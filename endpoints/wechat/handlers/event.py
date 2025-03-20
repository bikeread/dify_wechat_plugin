from typing import Dict, Any
import logging

from .base import MessageHandler
from ..models import WechatMessage

logger = logging.getLogger(__name__)


class EventMessageHandler(MessageHandler):
    """事件消息处理器"""

    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """
        处理事件消息并返回回复内容
        
        参数:
            message: 要处理的微信事件消息对象
            session: 当前会话对象，用于访问存储和AI接口
            app_settings: 应用设置字典
            
        返回:
            处理后的回复内容字符串
        """
        # 获取事件类型
        event_type = message.event
        logger.info(f"接收到事件消息，事件类型: {event_type}")

        # 根据事件类型调用不同的处理方法
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
        """处理关注事件"""
        logger.info(f"用户 {message.from_user} 关注了公众号")
        # 1. 获取会话ID
        conversation_id = self._get_conversation_id(session, self.get_storage_key(message.from_user))
        inputs = {
            "event": message.event,
            "msgType": message.msg_type,
        }
        content = "用户关注了公众号"

        # 2. 调用AI获取响应
        response_generator = self._invoke_ai(
            session, 
            app_settings, 
            content, 
            conversation_id, 
            inputs=inputs,
            user_id=message.from_user
        )

        # 3. 处理AI响应
        answer = self._process_ai_response(response_generator)

        # 4. 保存新的会话ID
        self.save_conversation_id(session, message.from_user)

        logger.info(f"处理完成，响应长度: {len(answer)}")

        return answer

    def _handle_unsubscribe_event(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """处理取消关注事件"""
        logger.info(f"用户 {message.from_user} 取消关注了公众号")
        # self.clear_cache(session, message.from_user)
        # 取消关注事件无需回复
        return ""

    def _handle_click_event(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """处理菜单点击事件"""
        event_key = getattr(message, 'event_key', '')
        logger.info(f"用户 {message.from_user} 点击了菜单，事件KEY: {event_key}")

        # 根据event_key处理不同的菜单点击事件
        if event_key == 'CLEAR_CONTEXT':
            # 清除上下文
            success = self.clear_cache(session, message.from_user)
            return "会话上下文已清除，您可以开始新的对话。" if success else "清除会话上下文失败，请稍后再试。"
        else:
            # 可以将菜单点击事件转发给AI处理
            return f"您点击了自定义菜单: {event_key}"

    def _handle_view_event(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """处理菜单跳转链接事件"""
        event_key = getattr(message, 'event_key', '')
        logger.info(f"用户 {message.from_user} 点击了菜单跳转链接，URL: {event_key}")
        # 跳转链接事件通常无需回复
        return ""

    def _handle_unknown_event(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """处理未知类型的事件"""
        event_type = getattr(message, 'event', 'unknown')
        logger.warning(f"收到未处理的事件类型: {event_type}")
        return ""
