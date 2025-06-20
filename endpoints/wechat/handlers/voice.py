import logging
import os
import tempfile
import base64
from typing import Dict, Any, Optional

from .base import MessageHandler
from ..models import WechatMessage
from ..api.media_manager import WechatMediaManager

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

class VoiceMessageHandler(MessageHandler):
    """voice message handler"""
    
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle voice message"""
        if message.recognition:
            logger.info(f"received voice message, voice recognition result: {message.recognition}")
        else:
            logger.info(f"received voice message, format: {message.format}, no recognition result")
        
        # 微信公众号配置
        app_id = app_settings.get("app_id")
        app_secret = app_settings.get("app_secret")
        wechat_api_proxy_url = app_settings.get("wechat_api_proxy_url")
        logger.info("application configuration: %s", app_settings)
        if not app_id or not app_secret:
            logger.error("missing wechat public account configuration")
            return "system configuration error"
            
        # try to get previous conversation id
        conversation_id = self._get_conversation_id(session, self.get_storage_key(message.from_user, app_settings.get("app").get("app_id")))

        # prepare input parameters
        inputs = {
            "msgId": message.msg_id,
            "msgType": message.msg_type,
            "fromUser": message.from_user,
            "media_id": message.media_id,
            "createTime": message.create_time,
        }
        
        # if there is a voice recognition result, use it directly
        if message.recognition:
            inputs["recognition"] = message.recognition
            query_text = message.recognition
        else:
            query_text = "this is a voice message"
        
        # get voice file content
        try:
            media_manager = WechatMediaManager(app_id, app_secret, wechat_api_proxy_url, session.storage)
            
            # check if using high-quality voice
            media_type = "jssdk" if message.format == "speex" else "normal"
            
            logger.info(f"start getting voice file, media_id: {message.media_id}, media_type: {media_type}")
            
            # get media content directly, without downloading to file
            result = media_manager.get_media(
                media_id=message.media_id,
                media_type=media_type
            )
            
            if result.get('success'):
                # get media type and content
                media_content = result.get('content')
                media_type_str = result.get('media_type', '')
                
                if media_content:
                    # encode binary content to Base64 string and pass to AI
                    voice_base64 = base64.b64encode(media_content).decode('utf-8')
                    
                    logger.info(f"voice file get successfully: {len(media_content)} bytes, type: {media_type_str}")
                    
                    # add encoded audio data and media type to inputs
                    inputs["voice_base64"] = voice_base64
                    inputs["voice_media_type"] = media_type_str
                    inputs["voice_format"] = message.format or "amr"
                else:
                    logger.error("voice file content is empty")
            else:
                logger.error(f"failed to get voice file: {result.get('error')}")
        except Exception as e:
            logger.error(f"failed to get voice file: {str(e)}")
        
        # invoke AI interface to process
        response_generator = self._invoke_ai(
            session, 
            app_settings,
            query_text,
            conversation_id,
            inputs=inputs,
            user_id=message.from_user
        )
        
        # process AI response
        ai_response = self._process_ai_response(response_generator)
        
        return ai_response
    