from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Optional
import time
import threading

from ..models import WechatMessage

logger = logging.getLogger(__name__)

# 定义超时常量
STREAM_CHUNK_TIMEOUT = 30  # 接收单个chunk的最大等待时间(秒)
MAX_TOTAL_STREAM_TIME = 240  # 流式处理的最大总时间(秒)


class MessageHandler(ABC):
    """消息处理器抽象基类"""
    def __init__(self):
        """初始化处理器"""
        self.initial_conversation_id = None
        self.new_conversation_id = None

    @abstractmethod
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """
        处理消息并返回回复内容
        
        参数:
            message: 要处理的微信消息对象
            session: 当前会话对象，用于访问存储和AI接口
            app_settings: 应用设置字典
            
        返回:
            处理后的回复内容字符串
        """
        pass

    def clear_cache(self, session: Any, user_id: str) -> bool:
        """
        清除指定用户的会话缓存
        
        参数:
            session: 当前会话对象，用于访问存储
            user_id: 用户标识（如微信用户的OpenID）
            
        返回:
            bool: 是否成功清除缓存
        """
        try:
            # 构造存储键
            storage_key = f"wechat_conv_{user_id}"
            logger.info(f"准备清除用户 '{user_id}' 的会话缓存，存储键: '{storage_key}'")

            # 删除会话数据
            session.storage.delete(storage_key)
            logger.info(f"已成功清除用户 '{user_id}' 的会话缓存")
            return True
        except Exception as e:
            logger.error(f"清除用户 '{user_id}' 的会话缓存失败: {str(e)}")
            return False

    def get_storage_key(self, user_id: str) -> str:
        """
        获取用户会话的存储键
        
        参数:
            user_id: 用户标识（如微信用户的OpenID）
            
        返回:
            str: 存储键
        """
        return f"wechat_conv_{user_id}"

    def _get_conversation_id(self, session: Any, storage_key: str) -> Optional[str]:
        """
        获取存储的会话ID
        
        参数:
            session: 当前会话对象，用于访问存储
            storage_key: 存储键
            
        返回:
            Optional[str]: 会话ID，如果不存在则返回None
        """
        try:
            stored_data = session.storage.get(storage_key)
            if stored_data:
                conversation_id = stored_data.decode('utf-8')
                logger.debug(f"使用已存在的会话ID: {conversation_id[:8]}...")
                return conversation_id
            logger.debug(f"未找到存储的会话ID(键:{storage_key})，将创建新对话")
            return None
        except Exception as e:
            logger.warning(f"获取存储的会话ID失败: {str(e)}")
            return None

    def _invoke_ai(self, session: Any, app: Dict[str, Any], content: str, conversation_id: Optional[str], inputs: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None) -> Any:
        """调用AI接口，获取流式响应生成器"""
        # 记录初始状态的conversation_id
        self.initial_conversation_id = conversation_id
        self.new_conversation_id = None

        # 准备调用参数
        invoke_params = {
            "app_id": app.get("app").get("app_id"),
            "query": content,
            "inputs": inputs or {},
            "response_mode": "streaming"
        }

        # 只有当获取到有效的conversation_id时才添加到参数中
        if conversation_id:
            invoke_params["conversation_id"] = conversation_id

        logger.debug(f"调用Dify API，参数: {invoke_params}")
        try:
            try:
                response_generator = session.app.chat.invoke(**invoke_params)
            except Exception as e:
                logger.error(f"调用Dify API失败: {str(e)}")
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    logger.error(f"API错误响应: {e.response.text}")
                raise

            # 获取第一个响应块
            first_chunk = next(response_generator)

            # 检查是否包含conversation_id
            if isinstance(first_chunk, dict) and 'conversation_id' in first_chunk:
                self.new_conversation_id = first_chunk['conversation_id']
                logger.debug(f"获取到新会话ID: {self.new_conversation_id[:8]}...")
                
                # 立即保存新的会话ID
                if session and hasattr(session, 'storage') and user_id and self.new_conversation_id != self.initial_conversation_id:
                    try:
                        storage_key = self.get_storage_key(user_id)
                        session.storage.set(storage_key, self.new_conversation_id.encode('utf-8'))
                        logger.info(f"已立即保存用户 '{user_id}' 的新会话ID")
                    except Exception as e:
                        logger.error(f"立即保存会话ID失败: {str(e)}")

            # 创建一个新的生成器，首先返回第一个块，然后返回原始生成器的其余部分
            def combined_generator():
                yield first_chunk
                yield from response_generator

            return combined_generator()
        except Exception as e:
            logger.error(f"调用AI接口失败: {str(e)}")
            return (x for x in [])

    def _process_ai_response(self, response_generator: Any) -> str:
        """处理AI接口流式响应"""
        if not response_generator:
            return "系统处理中，请稍后再试"

        start_time = time.time()
        chunk_count = 0
        full_content = ""

        try:
            # 遍历流式响应
            for chunk in self._safe_iterate(response_generator):
                chunk_count += 1

                # 检查块是否有效
                if not isinstance(chunk, dict):
                    continue

                # 处理消息内容
                if 'answer' in chunk:
                    full_content += chunk.get('answer', '')

                # 检查消息结束事件
                if chunk.get('event') == 'message_end':
                    message_end_received = True
                    break  # 收到结束事件后直接退出循环

            # 计算处理总时间
            total_time = time.time() - start_time

            logger.info(f"流式响应处理完成，共{chunk_count}个响应块，耗时: {total_time:.2f}秒")

            # 返回完整回复内容
            return full_content or "AI没有给出回复"
        except Exception as e:
            logger.error(f"处理流式响应时出错: {str(e)}")
            return f"处理AI回复时出现问题: {str(e)}"

    def _safe_iterate(self, response_generator):
        """安全地遍历生成器，添加超时保护"""
        done = False

        while not done:
            try:
                # 使用超时线程来防止无限阻塞
                chunk_received = [None]
                iteration_done = [False]
                exception_caught = [None]

                def get_next_chunk():
                    try:
                        chunk_received[0] = next(response_generator)
                    except StopIteration:
                        iteration_done[0] = True
                    except Exception as e:
                        exception_caught[0] = e

                # 创建获取下一个chunk的线程
                thread = threading.Thread(target=get_next_chunk)
                thread.daemon = True
                thread.start()

                # 等待线程完成或超时
                thread.join(timeout=STREAM_CHUNK_TIMEOUT)

                # 检查线程是否仍在运行（超时）
                if thread.is_alive():
                    logger.warning(f"获取流式响应块超时(已等待{STREAM_CHUNK_TIMEOUT}秒)")
                    done = True
                    break

                # 检查是否迭代结束
                if iteration_done[0]:
                    done = True
                    break

                # 检查是否有异常
                if exception_caught[0]:
                    logger.error(f"流式响应迭代出错: {exception_caught[0]}")
                    if hasattr(exception_caught[0], 'response') and hasattr(exception_caught[0].response, 'text'):
                        logger.error(f"API错误响应: {exception_caught[0].response.text}")
                    raise exception_caught[0]

                # 返回获取到的chunk
                yield chunk_received[0]

            except Exception as e:
                logger.error(f"迭代流式响应时出错: {str(e)}")
                done = True
                break

    def save_conversation_id(self, session: Any, user_id: str) -> None:
        """保存会话ID"""
        if self.new_conversation_id and self.new_conversation_id != self.initial_conversation_id:
            storage_key = self.get_storage_key(user_id)
            try:
                session.storage.set(storage_key, self.new_conversation_id.encode('utf-8'))
                logger.info(f"已保存用户 '{user_id}' 的新会话ID")
            except Exception as e:
                logger.error(f"保存会话ID失败: {str(e)}")
