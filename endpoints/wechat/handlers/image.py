import logging
from typing import Dict, Any, Optional

from .base import MessageHandler
from ..models import WechatMessage

logger = logging.getLogger(__name__)

class ImageMessageHandler(MessageHandler):
    """图片消息处理器"""
    
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """处理图片消息"""
        logger.info(f"接收到图片消息，图片URL: {message.pic_url}")
        
        # 获取应用配置
        app = app_settings.get("app")
        if not app:
            logger.error("缺少app配置")
            return "系统配置错误"
            
        # 尝试获取之前的会话ID
        conversation_id = self._get_conversation_id(session, self.get_storage_key(message.from_user))
        
        # 将图片信息转换为文本描述
        image_text = f"[图片] URL: {message.pic_url}"
        
        # 调用AI接口处理图片描述
        response_generator = self._invoke_ai(
            session, 
            app, 
            image_text, 
            conversation_id,
            user_id=message.from_user
        )
        
        # 处理AI响应
        ai_response = self._process_ai_response(response_generator)
        
        return ai_response
    
    def _invoke_ai(self, session: Any, app: Dict[str, Any], content: str, conversation_id: Optional[str], user_id: str) -> Dict[str, Any]:
        """调用AI接口"""
        # 记录初始状态的conversation_id
        self.initial_conversation_id = conversation_id
        self.new_conversation_id = None
        
        # 准备调用参数
        invoke_params = {
            "app_id": app.get("app_id"),
            "query": content,
            "inputs": {},
            "response_mode": "blocking"
        }
        
        # 只有当获取到有效的conversation_id时才添加到参数中
        if conversation_id:
            invoke_params["conversation_id"] = conversation_id
            logger.debug(f"使用现有的会话ID: {conversation_id[:8]}...")
        else:
            logger.debug("创建新的对话会话")
        
        # 调用AI接口
        try:
            logger.info(f"调用Dify API，参数: app_id={invoke_params['app_id']}" +
                        (f", conversation_id={conversation_id[:8]}..." if conversation_id else ", 新对话"))
            
            response_generator = session.app.chat.invoke(**invoke_params)
            
            # 获取第一个响应块
            first_chunk = next(response_generator)
            # 从响应中提取conversation_id
            if isinstance(first_chunk, dict) and 'conversation_id' in first_chunk:
                self.new_conversation_id = first_chunk['conversation_id']
                logger.debug(f"获取到新会话ID: {self.new_conversation_id[:8]}...")
            
            # 创建一个新的生成器，首先返回第一个块，然后返回原始生成器的其余部分
            def combined_generator():
                yield first_chunk
                yield from response_generator
            
            return combined_generator()
        except Exception as e:
            logger.error(f"调用AI接口失败: {str(e)}")
            return {}
    
    def _process_ai_response(self, response_generator: Dict[str, Any]) -> str:
        """处理AI接口响应"""
        if not isinstance(response_generator, dict):
            logger.warning(f"AI接口返回格式异常: {type(response_generator)}")
            return "系统处理中，请稍后再试"
            
        # 提取回复内容
        if 'answer' in response_generator:
            ai_response = response_generator.get('answer', '')
            logger.info(f"AI回复内容长度: {len(ai_response)}")
            return ai_response
        else:
            logger.warning(f"AI接口未返回预期格式: {response_generator}")
            return "系统处理中，请稍后再试" 