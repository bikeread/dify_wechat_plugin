import base64
import string
import random
import hashlib
import time
import struct
import json
from Crypto.Cipher import AES
import xml.etree.ElementTree as ET
import socket
import logging

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

class PKCS7Encoder:
    """provide encryption and decryption interfaces based on PKCS7 algorithm"""
    block_size = 32  # wechat official AES encryption uses 32-byte block size

    @staticmethod
    def encode(text):
        """fill and pad the plaintext to be encrypted
        @param text: plaintext to be filled and padded (bytes)
        @return: filled plaintext (bytes)
        """
        text_length = len(text)
        # calculate the number of bits to be padded
        amount_to_pad = PKCS7Encoder.block_size - (text_length % PKCS7Encoder.block_size)
        if amount_to_pad == 0:
            amount_to_pad = PKCS7Encoder.block_size
        # get the character used for padding
        pad_byte = bytes([amount_to_pad])
        padding = pad_byte * amount_to_pad
        # return the filled plaintext (bytes)
        return text + padding

    @staticmethod
    def decode(decrypted):
        """remove the padding character from the decrypted plaintext
        @param decrypted: decrypted plaintext (bytes)
        @return: plaintext without padding (bytes)
        """
        # in Python 3, the last byte of bytes is directly a number, no need to use ord()
        pad = decrypted[-1]
        if pad < 1 or pad > 32:
            pad = 0
        return decrypted[:-pad]


class WechatCrypto:
    """wechat message encryption and decryption tool class"""
    
    def __init__(self, token, encoding_aes_key, app_id):
        """
        initialize the encryption tool
        
        params:
            token: token of wechat public account configuration
            encoding_aes_key: EncodingAESKey of wechat public account
            app_id: AppID of wechat public account
        """
        self.token = token
        self.app_id = app_id
        # EncodingAESKey needs to be added with an equal sign for Base64 decoding
        self.aes_key = base64.b64decode(encoding_aes_key + "=")
        if len(self.aes_key) != 32:
            raise ValueError("invalid EncodingAESKey, decoded length must be 32 bytes")
        
    def encrypt_message(self, reply_msg, nonce, timestamp=None, format='xml'):
        """
        encrypt the reply message
        
        params:
            reply_msg: reply message string
            nonce: random string
            timestamp: timestamp (if None, use current time)
            format: return format, 'xml' or 'json'
            
        return:
            encrypted message string
        """
        if timestamp is None:
            timestamp = str(int(time.time()))
            
        # encrypt the message content
        encrypt = self._encrypt(reply_msg)
        
        # generate the security signature
        signature = self._gen_signature(timestamp, nonce, encrypt)
        
        # construct the result based on the specified format
        if format == 'json':
            result = self._gen_encrypted_json(encrypt, signature, timestamp, nonce)
        else:
            result = self._gen_encrypted_xml(encrypt, signature, timestamp, nonce)
        
        return result
        
    def decrypt_message(self, post_data, msg_signature, timestamp, nonce):
        """
        decrypt the wechat message
        
        params:
            post_data: received XML message data
            msg_signature: message signature
            timestamp: timestamp
            nonce: random string
            
        return:
            decrypted message string
        """
        try:
            # determine if it is XML or JSON
            if post_data.startswith('<'):
                # XML format
                xml_tree = ET.fromstring(post_data)
                encrypt = xml_tree.find("Encrypt").text
            else:
                # JSON format
                try:
                    json_data = json.loads(post_data)
                    encrypt = json_data.get("Encrypt", "")
                except:
                    logger.error("failed to parse JSON data")
                    raise ValueError("failed to parse data format")
            
            # verify the security signature
            signature = self._gen_signature(timestamp, nonce, encrypt)
            if signature != msg_signature:
                raise ValueError("signature verification failed")
            
            # decrypt
            decrypted = self._decrypt(encrypt)
            
            return decrypted
        except Exception as e:
            logger.error(f"failed to decrypt message: {str(e)}")
            raise
    
    def _encrypt(self, text):
        """
        encrypt the message
        """
        # ensure text is bytes type
        text_bytes = text.encode('utf-8') if isinstance(text, str) else text
        
        # add 16-bit random string to the beginning of the plaintext
        random_str_bytes = self._get_random_str().encode('utf-8')
        
        # process content length with network byte order
        network_order = struct.pack("I", socket.htonl(len(text_bytes)))
        
        # concatenate the plaintext
        app_id_bytes = self.app_id.encode('utf-8')
        content = random_str_bytes + network_order + text_bytes + app_id_bytes
        
        # use PKCS7 padding
        padded_content = PKCS7Encoder.encode(content)
        
        # encrypt
        cryptor = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        encrypted = cryptor.encrypt(padded_content)
        
        # Base64 encode
        return base64.b64encode(encrypted).decode('utf-8')
    
    def _decrypt(self, encrypted_text):
        """
        decrypt the encrypted message
        """
        try:
            # Base64 decode
            encrypted_data = base64.b64decode(encrypted_text)
            
            # decrypt
            cryptor = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
            decrypted_data = cryptor.decrypt(encrypted_data)
            
            # use PKCS7 to remove padding
            plain_bytes = PKCS7Encoder.decode(decrypted_data)
            
            # extract the message content
            content = plain_bytes[16:]  # remove the 16-bit random string
            xml_len = socket.ntohl(struct.unpack("I", content[:4])[0])
            xml_content = content[4:xml_len+4]
            from_appid = content[xml_len+4:].decode('utf-8')
            
            # verify the AppID
            if from_appid != self.app_id:
                raise ValueError(f"AppID verification failed: {from_appid} != {self.app_id}")
            
            return xml_content.decode('utf-8')
        except Exception as e:
            logger.error(f"failed to decrypt: {str(e)}")
            raise
    
    def _gen_signature(self, timestamp, nonce, encrypt):
        """
        generate the security signature
        """
        sign_list = [self.token, timestamp, nonce, encrypt]
        sign_list.sort()
        sign_str = ''.join(sign_list)
        
        # SHA1 encrypt
        sha = hashlib.sha1()
        sha.update(sign_str.encode('utf-8'))
        return sha.hexdigest()
    
    def _gen_encrypted_xml(self, encrypt, signature, timestamp, nonce):
        """
        generate the encrypted XML
        """
        xml = f"""<xml>
<Encrypt><![CDATA[{encrypt}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
        return xml
    
    def _gen_encrypted_json(self, encrypt, signature, timestamp, nonce):
        """
        generate the encrypted JSON
        """
        json_data = {
            "Encrypt": encrypt,
            "MsgSignature": signature,
            "TimeStamp": timestamp,
            "Nonce": nonce
        }
        return json.dumps(json_data)
    
    def _get_random_str(self, length=16):
        """
        generate a random string
        """
        rule = string.ascii_letters + string.digits
        return ''.join(random.sample(rule, length))


class WechatMessageCryptoAdapter:
    """wechat message encryption and decryption adapter"""
    
    def __init__(self, settings):
        """
        initialize the adapter
        
        params:
            settings: plugin configuration
        """
        # get the parameters needed for encryption from the configuration
        self.encoding_aes_key = settings.get('encoding_aes_key', '')
        self.app_id = settings.get('app_id', '')
        self.token = settings.get('wechat_token', '')
        
        # determine if encryption is needed based on whether encoding_aes_key exists
        self.is_encrypted_mode = bool(self.encoding_aes_key)
        
        # if it is encrypted mode, initialize the encryption tool
        if self.is_encrypted_mode:
            if not self.token or not self.app_id:
                raise ValueError("encryption mode requires token and app_id")
            
            self.crypto = WechatCrypto(self.token, self.encoding_aes_key, self.app_id)
        else:
            self.crypto = None
    
    def decrypt_message(self, request):
        """
        decrypt the request message
        
        params:
            request: request object
            
        return:
            decrypted XML string
        """
        raw_data = request.get_data(as_text=True)
        
        # plaintext mode returns directly
        if not self.is_encrypted_mode:
            logger.info("encryption mode is not enabled, returning plaintext")
            return raw_data
            
        # check if there is an encrypt_type parameter
        encrypt_type = request.args.get('encrypt_type', '')
        if encrypt_type != 'aes' and not request.args.get('msg_signature', ''):
            # no encryption type specified and no msg_signature parameter,视为明文
            logger.info("no encryption type specified and no msg_signature parameter, returning plaintext")
            return raw_data
            
        # encryption mode needs to be decrypted
        msg_signature = request.args.get('msg_signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        
        # check the completeness of the parameters
        if not msg_signature or not timestamp or not nonce:
            logger.warning("missing parameters for decryption")
            return raw_data
            
        # check if there is a msg_signature
        if not msg_signature:
            # in compatible mode, it may be a plaintext message
            # check if the XML has an Encrypt node or the JSON has an Encrypt field
            try:
                if raw_data.startswith('<'):
                    # XML format
                    xml_tree = ET.fromstring(raw_data)
                    encrypt_node = xml_tree.find("Encrypt")
                    if encrypt_node is None:
                        # no Encrypt node, considered as plaintext
                        return raw_data
                else:
                    # possibly JSON format
                    try:
                        json_data = json.loads(raw_data)
                        if 'Encrypt' not in json_data:
                            # no Encrypt field, considered as plaintext
                            return raw_data
                    except:
                        # not a valid JSON, considered as plaintext
                        return raw_data
            except:
                # parsing error, considered as plaintext
                return raw_data
            
        # decrypt the message
        try:
            logger.info("start decrypting message")
            return self.crypto.decrypt_message(raw_data, msg_signature, timestamp, nonce)
        except Exception as e:
            logger.error(f"failed to decrypt message: {str(e)}")
            # return plaintext when decryption fails, to avoid the entire request processing failure
            return raw_data
    
    def encrypt_message(self, reply_msg, request):
        """
        encrypt the reply message
        
        params:
            reply_msg: reply message string
            request: request object
            
        return:
            encrypted XML or JSON string
        """

        logger.info(f"reply_msg: {reply_msg}")
        # plaintext mode returns directly
        if not self.is_encrypted_mode:
            return reply_msg
            
        # check if encryption is needed (check the encrypt_type parameter in the URL)
        encrypt_type = request.args.get('encrypt_type', '')
        if encrypt_type != 'aes':
            # no encryption type specified, returning plaintext
            return reply_msg
            
        # determine the return format
        content_type = request.headers.get('Content-Type', '')
        format = 'json' if 'application/json' in content_type else 'xml'
        
        # encryption mode needs to be encrypted
        nonce = request.args.get('nonce', '')
        timestamp = request.args.get('timestamp', '')
        
        # check the completeness of the parameters
        if not nonce or not timestamp:
            logger.warning("missing parameters for encryption")
            return reply_msg
            
        try:
            encrypted_msg = self.crypto.encrypt_message(reply_msg, nonce, timestamp, format)
            return encrypted_msg
        except Exception as e:
            logger.error(f"failed to encrypt message: {str(e)}")
            # return plaintext when encryption fails, to avoid the response failure
            return reply_msg 