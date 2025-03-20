import logging
import traceback
from typing import Dict, Any
from abc import ABC

from .base import MessageHandler
from ..models import WechatMessage

logger = logging.getLogger(__name__)

class TextMessageHandler(MessageHandler):
    """文本消息处理器"""
    
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """
        处理文本消息并返回回复内容
        
        参数:
            message: 要处理的微信文本消息对象
            session: 当前会话对象，用于访问存储和AI接口
            app_settings: 应用设置字典
            
        返回:
            处理后的回复内容字符串
        """
        try:
            # 记录开始处理
            logger.info(f"开始处理用户'{message.from_user}'的文本消息: '{message.content[:50]}...'")
            
            # 1. 获取会话ID
            conversation_id = self._get_conversation_id(session, self.get_storage_key(message.from_user))

            inputs = {
                "msgId": message.msg_id,
                "msgType": message.msg_type,
            }
            # 2. 调用AI获取响应
            response_generator = self._invoke_ai(
                session, 
                app_settings, 
                message.content, 
                conversation_id,
                inputs=inputs,
                user_id=message.from_user
            )
            
            # 3. 处理AI响应
            answer = self._process_ai_response(response_generator)
            
            logger.info(f"处理完成，响应长度: {len(answer)}")
            
            return answer
        except Exception as e:
            logger.error(f"处理文本消息失败: {str(e)}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"异常堆栈: {traceback.format_exc()}")
            return f"抱歉，处理您的消息时出现了问题: {str(e)}"