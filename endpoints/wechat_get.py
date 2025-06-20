import time
import hashlib
import logging
from typing import Mapping
from werkzeug import Request, Response
from dify_plugin import Endpoint

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)


class WechatGet(Endpoint):
    """wechat public account server verification endpoint"""
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        handle the wechat public account token verification request
        """
        # get the parameters sent by wechat
        signature = r.args.get('signature', '')
        timestamp = r.args.get('timestamp', '')
        nonce = r.args.get('nonce', '')
        echostr = r.args.get('echostr', '')
        
        # get the token from the configuration
        token = settings.get('wechat_token', '')
        
        if not token:
            logger.error("wechat token not configured")
            return Response("wechat token not configured", status=500)
        
        # check if it is encrypted mode
        encoding_aes_key = settings.get('encoding_aes_key', '')
        is_encrypted_mode = bool(encoding_aes_key)
        
        # check if there is a msg_signature parameter
        msg_signature = r.args.get('msg_signature', '')
        
        # handle the verification in encrypted mode
        if is_encrypted_mode and msg_signature:
            app_id = settings.get('app_id', '')
            
            if not app_id:
                logger.error("missing app_id configuration in encrypted mode")
                return Response("configuration error", status=500)
                
            # the verification logic in encrypted mode
            try:
                from endpoints.wechat.crypto import WechatCrypto
                crypto = WechatCrypto(token, encoding_aes_key, app_id)
                
                # decrypt echostr
                echostr = crypto.decrypt_message(f"<xml><Encrypt><![CDATA[{echostr}]]></Encrypt></xml>", 
                                                msg_signature, timestamp, nonce)
                
                # return the decrypted echostr
                return Response(echostr, status=200)
            except Exception as e:
                logger.error(f"failed to decrypt echostr: {str(e)}")
                return Response("verification failed", status=403)
        else:
            # regular verification mode            
            # according to the verification rules of wechat
            # 1. sort the token, timestamp, nonce parameters in dictionary order
            temp_list = [token, timestamp, nonce]
            temp_list.sort()
            
            # 2. concatenate the three parameters into a string and encrypt it using sha1
            temp_str = ''.join(temp_list)
            hash_object = hashlib.sha1(temp_str.encode('utf-8'))
            hash_str = hash_object.hexdigest()
            
            # 3. compare the encrypted string with signature, if they are the same, return echostr
            if hash_str == signature:
                return Response(echostr, status=200)
            else:
                logger.warning(f"verification failed: calculated signature={hash_str}, received signature={signature}")
                return Response("verification failed", status=403)
