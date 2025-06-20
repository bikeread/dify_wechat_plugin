import logging
from typing import Dict, Any, Optional

from .base import MessageHandler
from ..models import WechatMessage

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

class ImageMessageHandler(MessageHandler):
    """image message handler"""
    
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle image message"""
        logger.info(f"received image message, image URL: {message.pic_url}")
        
        # get application configuration
        app = app_settings.get("app")
        if not app:
            logger.error("missing app configuration")
            return "system configuration error"
            
        # try to get previous conversation id
        conversation_id = self._get_conversation_id(session, self.get_storage_key(message.from_user, app.get("app_id")))
        
        # convert image information to text description
        image_text = f"[image] URL: {message.pic_url}"

        inputs = {
            "msgId": message.msg_id,
            "msgType": message.msg_type,
            "fromUser": message.from_user,
            "createTime": message.create_time,
            "picUrl": message.pic_url
        }

        # invoke AI interface to process image description
        response_generator = self._invoke_ai(
            session, 
            app_settings,
            image_text, 
            conversation_id,
            inputs=inputs,
            user_id=message.from_user
        )
        
        # process AI response
        ai_response = self._process_ai_response(response_generator)
        
        return ai_response