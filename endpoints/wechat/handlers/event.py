from typing import Dict, Any
import logging

from .base import MessageHandler
from ..models import WechatMessage

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)


class EventMessageHandler(MessageHandler):
    """event message handler"""

    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """
        handle event message and return reply content
        
        params:
            message: wechat event message object to handle
            session: current session object for accessing storage and AI interface
            app_settings: application settings dictionary
            
        return:
            processed reply content string
        """
        # get event type
        event_type = message.event
        logger.info(f"received event message, event type: {event_type}")

        # call different processing methods based on event type
        if event_type == 'subscribe':
            return self._handle_subscribe_event(message, session, app_settings)
        elif event_type == 'unsubscribe':
            return self._handle_unsubscribe_event(message, session, app_settings)
        elif event_type == 'CLICK':
            return self._handle_click_event(message, session, app_settings)
        elif event_type == 'VIEW':
            return self._handle_view_event(message, session, app_settings)
        else:
            return self._handle_unknown_event(message, session, app_settings)

    def _handle_subscribe_event(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle subscribe event"""
        logger.info(f"user {message.from_user} subscribed to the public account")
        # 1. get conversation id
        conversation_id = self._get_conversation_id(session, self.get_storage_key(message.from_user, app_settings.get("app").get("app_id")))
        inputs = {
            "event": message.event,
            "msgType": message.msg_type,
        }
        content = "user subscribed to the public account"

        # 2. invoke AI to get response
        response_generator = self._invoke_ai(
            session, 
            app_settings, 
            content, 
            conversation_id, 
            inputs=inputs,
            user_id=message.from_user
        )

        # 3. process AI response
        answer = self._process_ai_response(response_generator)

        # 4. save new conversation id
        self.save_conversation_id(session, message.from_user, app_settings.get("app").get("app_id"))

        logger.info(f"processed, response length: {len(answer)}")

        return answer

    def _handle_unsubscribe_event(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle unsubscribe event"""
        logger.info(f"user {message.from_user} unsubscribed from the public account")
        # self.clear_cache(session, message.from_user)
        # unsubscribe event does not need to reply
        return ""

    def _handle_click_event(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle menu click event"""
        event_key = getattr(message, 'event_key', '')
        logger.info(f"user {message.from_user} clicked the menu, event key: {event_key}")

        # 根据event_key处理不同的菜单点击事件
        if event_key == 'CLEAR_CONTEXT':
            # clear context
            success = self.clear_cache(session, message.from_user, app_settings.get("app").get("app_id"))
            return "conversation context has been cleared, you can start a new conversation." if success else "failed to clear conversation context, please try again later."
        else:
            # forward menu click event to AI processing
            return f"you clicked the custom menu: {event_key}"

    def _handle_view_event(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle menu redirect link event"""
        event_key = getattr(message, 'event_key', '')
        logger.info(f"user {message.from_user} clicked the menu redirect link, URL: {event_key}")
        # redirect link event usually does not need to reply
        return ""

    def _handle_unknown_event(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle unknown event type"""
        event_type = getattr(message, 'event', 'unknown')
        logger.warning(f"received unknown event type: {event_type}")
        return ""
