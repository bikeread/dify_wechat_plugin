import logging
import threading
import time
from typing import Dict, Any, Optional


# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

# 默认配置常量
DEFAULT_WAITING_EXPIRE = 30  # 等待状态过期时间（秒）
DEFAULT_FINAL_TIMEOUT_MESSAGE = "处理时间较长，请稍后重新询问"  # 最终超时提示消息

class UserWaitingManager:
    """
    用户等待状态管理器
    用于管理用户的继续等待状态
    """
    # 类变量，用于存储所有等待中的用户
    _waiting_users: Dict[str, Dict[str, Any]] = {}
    
    # 字典操作锁
    _waiting_lock = threading.Lock()
    
    # 清理线程标志
    _cleanup_thread_started = False
    
    @classmethod
    def set_user_waiting(cls, user_openid: str, original_message_status: Dict[str, Any], 
                        max_continue_count: int = 2) -> None:
        """
        设置用户为等待继续状态
        
        params:
            user_openid: 用户OpenID
            original_message_status: 原始消息处理状态
            max_continue_count: 最大继续等待次数
        """
        with cls._waiting_lock:
            cls._waiting_users[user_openid] = {
                'original_status': original_message_status,
                'start_time': time.time(),
                'expire_time': time.time() + DEFAULT_WAITING_EXPIRE,
                'continue_count': 0,
                'max_continue_count': max_continue_count,
                'lock': threading.Lock()  # 每个用户独立的锁
            }
            
            logger.info(f"用户 {user_openid} 设置为等待继续状态，最大次数: {max_continue_count}")
            
            # 确保清理线程已启动
            cls._ensure_cleanup_thread()
    
    @classmethod
    def is_user_waiting(cls, user_openid: str) -> bool:
        """
        检查用户是否在等待继续状态
        
        params:
            user_openid: 用户OpenID
            
        return:
            是否在等待状态
        """
        with cls._waiting_lock:
            if user_openid not in cls._waiting_users:
                return False
            
            waiting_info = cls._waiting_users[user_openid]
            
            # 检查是否过期
            if time.time() > waiting_info['expire_time']:
                logger.info(f"用户 {user_openid} 等待状态已过期，自动清理")
                cls._waiting_users.pop(user_openid, None)
                return False
            
            return True
    
    @classmethod
    def handle_continue_request(cls, user_openid: str) -> Optional[Dict[str, Any]]:
        """
        处理用户的继续请求
        
        params:
            user_openid: 用户OpenID
            
        return:
            等待信息字典，如果用户不在等待状态则返回None
        """
        with cls._waiting_lock:
            if user_openid not in cls._waiting_users:
                logger.warning(f"用户 {user_openid} 不在等待状态，无法处理继续请求")
                return None
            
            waiting_info = cls._waiting_users[user_openid]
            
            # 检查是否过期
            if time.time() > waiting_info['expire_time']:
                logger.info(f"用户 {user_openid} 等待状态已过期")
                cls._waiting_users.pop(user_openid, None)
                return None
            
            # 使用用户独立锁更新状态
            with waiting_info['lock']:
                waiting_info['continue_count'] += 1
                logger.info(f"用户 {user_openid} 继续等待请求，当前次数: {waiting_info['continue_count']}")
                
                # 返回副本，排除锁对象
                return {k: v for k, v in waiting_info.items() if k != 'lock'}
    
    @classmethod
    def clear_user_waiting(cls, user_openid: str) -> bool:
        """
        清除用户等待状态
        
        params:
            user_openid: 用户OpenID
            
        return:
            是否成功清除
        """
        with cls._waiting_lock:
            if user_openid in cls._waiting_users:
                cls._waiting_users.pop(user_openid, None)
                logger.info(f"用户 {user_openid} 等待状态已清除")
                return True
            return False
    
    @classmethod
    def get_waiting_info(cls, user_openid: str) -> Optional[Dict[str, Any]]:
        """
        获取用户等待信息
        
        params:
            user_openid: 用户OpenID
            
        return:
            等待信息字典或None
        """
        with cls._waiting_lock:
            if user_openid not in cls._waiting_users:
                return None
            
            waiting_info = cls._waiting_users[user_openid]
            
            # 检查是否过期
            if time.time() > waiting_info['expire_time']:
                cls._waiting_users.pop(user_openid, None)
                return None
            
            # 返回副本，排除锁对象
            return {k: v for k, v in waiting_info.items() if k != 'lock'}
    
    @classmethod
    def get_waiting_count(cls) -> int:
        """
        获取当前等待中的用户数量
        
        return:
            等待中的用户数量
        """
        with cls._waiting_lock:
            return len(cls._waiting_users)
    
    @classmethod
    def _ensure_cleanup_thread(cls) -> None:
        """确保清理线程已启动"""
        if not cls._cleanup_thread_started:
            cls._cleanup_thread_started = True
            thread = threading.Thread(
                target=cls._cleanup_expired_waiting,
                daemon=True,
                name="UserWaitingCleanupThread"
            )
            thread.start()
            logger.info("用户等待状态清理线程已启动")
    
    @classmethod
    def _cleanup_expired_waiting(cls) -> None:
        """定期清理过期的等待状态"""
        try:
            while True:
                # 每30秒清理一次
                time.sleep(30)
                
                with cls._waiting_lock:
                    now = time.time()
                    expired_users = [
                        user_id for user_id, waiting_info in cls._waiting_users.items()
                        if now > waiting_info['expire_time']
                    ]
                    
                    # 删除过期的等待状态
                    for user_id in expired_users:
                        cls._waiting_users.pop(user_id, None)
                    
                    if expired_users:
                        logger.info(f"清理了 {len(expired_users)} 个过期的用户等待状态，剩余: {len(cls._waiting_users)}")
        
        except Exception as e:
            logger.error(f"用户等待状态清理线程异常退出: {str(e)}")
            cls._cleanup_thread_started = False 