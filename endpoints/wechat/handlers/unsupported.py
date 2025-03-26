import logging
from typing import Dict, Any

from .base import MessageHandler
from ..models import WechatMessage

logger = logging.getLogger(__name__)

class UnsupportedMessageHandler(MessageHandler):
    """unsupported message type handler"""
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle unsupported message type"""
        logger.warning(f"unsupported message type: {message.msg_type}")
        return "currently only text messages are supported" 