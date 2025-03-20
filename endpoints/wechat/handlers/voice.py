import logging
from typing import Dict, Any, Optional

from .base import MessageHandler
from ..models import WechatMessage

logger = logging.getLogger(__name__)

class VoiceMessageHandler(MessageHandler):
    """语音消息处理器"""
    
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """处理语音消息"""
        if message.recognition:
            logger.info(f"接收到语音消息，语音识别结果: {message.recognition}")
        else:
            logger.info(f"接收到语音消息，格式: {message.format}，无识别结果")
        
        # 获取应用配置
        app = app_settings.get("app")
        if not app:
            logger.error("缺少app配置")
            return "系统配置错误"
            
        # 构建存储键
        storage_key = self.get_storage_key(message.from_user)
        
        # 尝试获取之前的会话ID
        conversation_id = self._get_conversation_id(session, storage_key)
        
        # 处理语音消息
        # 如果有语音识别结果，使用识别结果作为文本输入
        # 否则告知用户无法识别语音内容
        if message.recognition:
            voice_text = message.recognition
            prefix = "您的语音内容：\n"
        else:
            voice_text = "您发送了一条语音消息，但我无法识别其中的内容。请尝试发送文字消息。"
            prefix = ""

        inputs = {
            "msgId": message.msg_id,
            "msgType": message.msg_type,
        }
        # 调用AI接口处理语音识别文本
        response_generator = self._invoke_ai(
            session, 
            app, 
            voice_text, 
            conversation_id,
            inputs=inputs,
            user_id=message.from_user
        )
        
        # 处理AI响应
        ai_response = self._process_ai_response(response_generator)
        
        # 处理结果
        full_response = f"{prefix}{ai_response}" if ai_response else "抱歉，我无法处理您的语音信息"
        return full_response
    