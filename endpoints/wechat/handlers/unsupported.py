import logging
from typing import Dict, Any

from .base import MessageHandler
from ..models import WechatMessage

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

class UnsupportedMessageHandler(MessageHandler):
    """unsupported message type handler"""
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """handle unsupported message type"""
        logger.warning(f"unsupported message type: {message.msg_type}")
        return "currently only text messages are supported" 