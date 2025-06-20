import logging
import threading
import time
from typing import Dict, Any, Optional, Union

from .models import WechatMessage

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

class MessageStatusTracker:
    """
    message status tracker
    used to track the processing status and retry mechanism of wechat messages
    """
    # class variable, used to store all messages being processed
    _messages: Dict[str, Dict[str, Any]] = {}
    
    # dictionary operation lock
    _messages_lock = threading.Lock()
    
    @classmethod
    def track_message(cls, message: Union[WechatMessage, str]) -> Dict[str, Any]:
        """
        track a message, if the message exists, update the retry count and return its status, otherwise create a new status
        
        params:
            message: WechatMessage object or message ID string
            
        return:
            the status of the message
        """
        tracking_id = cls._get_tracking_id(message)
        if not tracking_id:
            return cls._create_temp_status()
        
        with cls._messages_lock:
            # check if the message exists
            if tracking_id in cls._messages:
                # increment the retry count
                cls._messages[tracking_id]['retry_count'] = cls._messages[tracking_id].get('retry_count', 0) + 1
                retry_count = cls._messages[tracking_id]['retry_count']
                logger.info(f"detected retry request: {tracking_id}, current retry count: {retry_count}")
                return cls._messages[tracking_id]
            
            # new message, create status
            status = cls._create_status()
            cls._messages[tracking_id] = status
            
            # start cleanup thread (if not started)
            cls._ensure_cleanup_thread()
            
            return status
    
    @classmethod
    def update_status(cls, message: Union[WechatMessage, str], result: Optional[str] = None, 
                     is_completed: bool = False, error: Optional[str] = None) -> None:
        """
        update the processing status of the message
        
        params:
            message: WechatMessage object or message ID string
            result: processing result
            is_completed: whether the processing is completed
            error: error information
        """
        tracking_id = cls._get_tracking_id(message)
        if not tracking_id:
            return
        
        with cls._messages_lock:
            if tracking_id not in cls._messages:
                cls._messages[tracking_id] = cls._create_status()
            
            status = cls._messages[tracking_id]
            
            # use message independent lock to update status
            with status['lock']:
                # update status
                if result is not None:
                    status['result'] = result
                
                if error is not None:
                    status['error'] = error
                
                if is_completed:
                    status['is_completed'] = True
                    # set completion event
                    if 'completion_event' in status and not status['completion_event'].is_set():
                        status['completion_event'].set()
    
    @classmethod
    def mark_result_returned(cls, message: Union[WechatMessage, str]) -> bool:
        """
        atomic operation: mark the result as returned
        if the result has been marked as returned, return False
        if successfully marked, return True
        
        params:
            message: WechatMessage object or message ID string
        """
        tracking_id = cls._get_tracking_id(message)
        if not tracking_id:
            return False
        
        with cls._messages_lock:
            if tracking_id not in cls._messages:
                return False
            
            status = cls._messages[tracking_id]
            
            # use message independent lock to update status
            with status['lock']:
                if status.get('result_returned', False):
                    logger.debug(f"result has been marked as returned, skipping processing: {tracking_id}")
                    return False
                
                status['result_returned'] = True
                return True
    
    @classmethod
    def increment_retry(cls, message: Union[WechatMessage, str]) -> int:
        """
        increment the retry count of the message
        return the incremented retry count
        
        params:
            message: WechatMessage object or message ID string
        """
        tracking_id = cls._get_tracking_id(message)
        if not tracking_id:
            return 0
        
        with cls._messages_lock:
            if tracking_id not in cls._messages:
                cls._messages[tracking_id] = cls._create_status()
            
            status = cls._messages[tracking_id]
            
            # use message independent lock to update status
            with status['lock']:
                status['retry_count'] = status.get('retry_count', 0) + 1
                return status['retry_count']
    
    @classmethod
    def get_status(cls, message: Union[WechatMessage, str]) -> Optional[Dict[str, Any]]:
        """
        get the processing status of the message
        
        params:
            message: WechatMessage object or message ID string
        """
        tracking_id = cls._get_tracking_id(message)
        if not tracking_id:
            return None
        
        with cls._messages_lock:
            if tracking_id not in cls._messages:
                return None
            
            # return a shallow copy of the status, excluding the lock object
            return {k: v for k, v in cls._messages[tracking_id].items() 
                   if k not in ('lock', 'completion_event')}
    
    @classmethod
    def wait_for_completion(cls, message: Union[WechatMessage, str], timeout: Optional[float] = None) -> bool:
        """
        wait for the message to be processed
        
        params:
            message: WechatMessage object or message ID string
            timeout: waiting timeout
        """
        tracking_id = cls._get_tracking_id(message)
        if not tracking_id:
            return False
        
        completion_event = None
        
        with cls._messages_lock:
            if tracking_id not in cls._messages:
                return False
            
            status = cls._messages[tracking_id]
            
            # if completed, return directly
            if status.get('is_completed', False):
                return True
            
            # get completion event
            completion_event = status.get('completion_event')
        
        # wait for completion outside the lock
        if completion_event:
            return completion_event.wait(timeout=timeout)
        
        return False
    
    @classmethod
    def _get_tracking_id(cls, message: Union[WechatMessage, str]) -> Optional[str]:
        """
        get the tracking ID based on the message type
        
        params:
            message: WechatMessage object or message ID string
        
        return:
            tracking ID or None
        """
        if isinstance(message, str):
            return message
        
        # if it is a WechatMessage object
        if hasattr(message, 'msg_type'):
            # for event messages, use from_user + event + create_time as identifier
            if message.msg_type == 'event':
                tracking_id = f"{message.from_user}_{message.event}_{message.create_time}"
                logger.debug(f"event message uses custom identifier: {tracking_id}")
                return tracking_id
            # for normal messages, use msg_id
            elif hasattr(message, 'msg_id') and message.msg_id:
                return message.msg_id
        
        logger.warning(f"failed to get tracking ID for message: {message}")
        return None
    
    @classmethod
    def _create_status(cls) -> Dict[str, Any]:
        """create a new status object"""
        return {
            'result': None,
            'is_completed': False,
            'error': None,
            'start_time': time.time(),
            'completion_event': threading.Event(),
            'retry_count': 0,
            'result_returned': False,  # mark if the result has been sent
            'lock': threading.Lock(),   # each message independent lock
            # 新增继续请求相关字段
            'is_continue_request': False,      # 是否为继续请求
            'continue_round': 0,               # 继续轮次
            'parent_message_id': None,         # 父消息ID（原始消息）
        }
    
    @classmethod
    def _create_temp_status(cls) -> Dict[str, Any]:
        """create a temporary status object (not tracked)"""
        return cls._create_status()
    
    @classmethod
    def _ensure_cleanup_thread(cls) -> None:
        """ensure the cleanup thread has been started"""
        if not hasattr(cls, '_cleanup_thread_started') or not cls._cleanup_thread_started:
            cls._cleanup_thread_started = True
            thread = threading.Thread(
                target=cls._cleanup_expired_messages,
                daemon=True,
                name="MessageCleanupThread"
            )
            thread.start()
    
    @classmethod
    def _cleanup_expired_messages(cls) -> None:
        """clean up expired messages periodically"""
        try:
            while True:
                # clean up every 60 seconds
                time.sleep(60)
                
                with cls._messages_lock:
                    now = time.time()
                    # clean up completed messages that have been over 10 minutes
                    expired_keys = [
                        msg_id for msg_id, status in cls._messages.items()
                        if status.get('is_completed', False) and 
                           now - status.get('start_time', now) > 600  # 10 minutes
                    ]
                    
                    # delete expired messages
                    for msg_id in expired_keys:
                        cls._messages.pop(msg_id, None)
                    
                    if expired_keys:
                        logger.info(f"cleaned up {len(expired_keys)} expired messages, remaining messages: {len(cls._messages)}")
        except Exception as e:
            logger.error(f"message cleanup thread exited abnormally: {str(e)}")
            cls._cleanup_thread_started = False

# backward compatible alias
MessageRetryTracker = MessageStatusTracker 