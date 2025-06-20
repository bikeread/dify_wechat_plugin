import logging
import traceback
from typing import Dict, Any
from abc import ABC

from .base import MessageHandler
from ..models import WechatMessage

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

class TextMessageHandler(MessageHandler):
    """text message handler"""
    
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """
        handle text message and return reply content
        
        params:
            message: wechat text message object to handle
            session: current session object for accessing storage and AI interface
            app_settings: application settings dictionary
            
        return:
            processed reply content string
        """
        try:
            # record start processing
            logger.info(f"start processing user's text message: '{message.content[:50]}...'")
            
            # 1. get conversation id
            conversation_id = self._get_conversation_id(session, self.get_storage_key(message.from_user, app_settings.get("app").get("app_id")))

            inputs = {
                "msgId": message.msg_id,
                "msgType": message.msg_type,
                "fromUser": message.from_user,
                "media_id": message.media_id,
                "createTime": message.create_time,
            }
            # 2. invoke AI to get response
            response_generator = self._invoke_ai(
                session, 
                app_settings, 
                message.content, 
                conversation_id,
                inputs=inputs,
                user_id=message.from_user
            )
            
            # 3. process AI response
            answer = self._process_ai_response(response_generator)
            
            logger.info(f"processed, response length: {len(answer)}")
            
            return answer
        except Exception as e:
            logger.error(f"failed to handle text message: {str(e)}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"exception stack: {traceback.format_exc()}")
            return f"sorry, there was an issue processing your message: {str(e)}"