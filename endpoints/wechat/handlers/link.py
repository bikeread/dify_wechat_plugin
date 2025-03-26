import logging
from typing import Dict, Any, Optional

from .base import MessageHandler
from ..models import WechatMessage

logger = logging.getLogger(__name__)

class LinkMessageHandler(MessageHandler):
    """link message handler"""
    
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle link message"""
        logger.info(f"received link message, title: {message.title}, URL: {message.url}")
        
        # get application configuration
        app = app_settings.get("app")
        if not app:
            logger.error("missing app configuration")
            return "system configuration error"
            
        # try to get previous conversation id
        conversation_id = self._get_conversation_id(session, self.get_storage_key(message.from_user, app.get("app_id")))

        # convert link information to text description
        link_text = f"[link] title: {message.title}\ndescription: {message.description or 'no description'}\nURL: {message.url}"

        inputs = {
            "msgId": message.msg_id,
            "msgType": message.msg_type,
            "fromUser": message.from_user,
            "createTime": message.create_time,
            "url": message.url,
            "title": message.title,
            "description": message.description,
        }

        # invoke AI interface to process link description
        response_generator = self._invoke_ai(
            session, 
            app, 
            link_text, 
            conversation_id,
            inputs=inputs,
            user_id=message.from_user
        )
        
        # process AI response
        ai_response = self._process_ai_response(response_generator)
        
        return ai_response