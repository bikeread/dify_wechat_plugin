import logging
import threading
import time
from typing import Mapping
from werkzeug import Request, Response
from dify_plugin import Endpoint

from endpoints.wechat.handlers import MessageHandler
# import the split components
from endpoints.wechat.parsers import MessageParser
from endpoints.wechat.factory import MessageHandlerFactory
from endpoints.wechat.formatters import ResponseFormatter
from endpoints.wechat.crypto import WechatMessageCryptoAdapter
from endpoints.wechat.api import WechatCustomMessageSender
# import the retry tracker
from endpoints.wechat.retry_tracker import MessageStatusTracker
# import the waiting manager
from endpoints.wechat.waiting_manager import UserWaitingManager

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

# default timeout and response settings
DEFAULT_HANDLER_TIMEOUT = 5.0  # default timeout time 5.0 seconds, fixed value
DEFAULT_TEMP_RESPONSE = "内容生成耗时较长，请稍等..."  # default temporary response message
# retry waiting time, will be dynamically updated based on configuration
DEFAULT_RETRY_WAIT_TIMEOUT_RATIO = 0.7  # 默认重试等待超时系数
RETRY_WAIT_TIMEOUT = DEFAULT_HANDLER_TIMEOUT * DEFAULT_RETRY_WAIT_TIMEOUT_RATIO
# clear history identifier message
CLEAR_HISTORY_MESSAGE = "/clear"

# 新增默认配置项
DEFAULT_ENABLE_CUSTOM_MESSAGE = False  # 默认不启用客服消息
DEFAULT_CONTINUE_MESSAGE = "生成答复中，继续等待请回复1"
DEFAULT_MAX_CONTINUE_COUNT = 2


class WechatPost(Endpoint):
    """wechat public account message processing endpoint"""
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """handle wechat request"""
        # 记录关键配置信息（仅在DEBUG模式下显示详细信息）
        logger.debug(f"微信请求: {r.method} {r.url}")
        logger.debug(f"配置: {settings}")

        # 1. get the temporary response message from the configuration
        temp_response_message = settings.get('timeout_message') or DEFAULT_TEMP_RESPONSE
        
        # 获取新增配置项，如果配置值为None则使用默认值
        enable_custom_message = settings.get('enable_custom_message') or DEFAULT_ENABLE_CUSTOM_MESSAGE
        continue_waiting_message = settings.get('continue_waiting_message') or DEFAULT_CONTINUE_MESSAGE
        max_continue_count = int(settings.get('max_continue_count') or DEFAULT_MAX_CONTINUE_COUNT)
        
        # 获取重试等待超时系数配置并更新全局变量
        retry_wait_timeout_ratio = float(settings.get('retry_wait_timeout_ratio') or DEFAULT_RETRY_WAIT_TIMEOUT_RATIO)
        # 确保系数在合理范围内
        retry_wait_timeout_ratio = max(0.1, min(1.0, retry_wait_timeout_ratio))
        global RETRY_WAIT_TIMEOUT
        RETRY_WAIT_TIMEOUT = DEFAULT_HANDLER_TIMEOUT * retry_wait_timeout_ratio
        
        try:
            # 2. create the encryption adapter
            crypto_adapter = WechatMessageCryptoAdapter(settings)
            
            # 3. decrypt the message
            try:
                decrypted_data = crypto_adapter.decrypt_message(r)
            except Exception as e:
                logger.error(f"消息解密失败: {str(e)}")
                return Response('decryption failed', status=400)
                
            # 4. parse the message content
            message = MessageParser.parse_xml(decrypted_data)
            # create the handler and call the clear cache method
            handler = MessageHandlerFactory.get_handler(message.msg_type)
            
            # if the clear history instruction is received
            if message.content == CLEAR_HISTORY_MESSAGE:
                success = handler.clear_cache(self.session, message.from_user, settings.get("app").get("app_id"))
                logger.info(f"清理历史记录: {'成功' if success else '失败'}")
                
                result_message = "history chat records have been cleared" if success else "failed to clear history records, please try again later"
                response_xml = ResponseFormatter.format_xml(message, result_message)
                encrypted_response = crypto_adapter.encrypt_message(response_xml, r)
                return Response(encrypted_response, status=200, content_type="application/xml")

            # 5. use MessageStatusTracker to track the message status
            # directly pass the message object, let the tracker decide which identifier to use
            message_status = MessageStatusTracker.track_message(message)
            retry_count = message_status.get('retry_count', 0)
            
            # 检查是否为继续等待请求，添加特殊标记
            if (message.content == "1" and 
                not enable_custom_message and 
                UserWaitingManager.is_user_waiting(message.from_user)):
                waiting_info = UserWaitingManager.get_waiting_info(message.from_user)
                if waiting_info:
                    message_status['is_continue_waiting'] = True
                    message_status['original_waiting_info'] = waiting_info
                    logger.info(f"检测到继续等待请求，当前等待次数: {waiting_info['continue_count']}")
            
            # initialize the result returned flag
            message_status['result_returned'] = False
            
            # 6. handle the retry request
            if retry_count > 0:
                logger.info(f"微信重试请求: 第{retry_count}次")
                return self._handle_retry(message, message_status, retry_count, 
                                        temp_response_message, enable_custom_message, 
                                        continue_waiting_message, max_continue_count, 
                                        crypto_adapter, r)
            
            # 7. handle the first request
            return self._handle_first_request(message, message_status, settings, 
                                            handler, enable_custom_message, crypto_adapter, r)
        except Exception as e:
            logger.error(f"处理请求异常: {e}")
            return Response("", status=200, content_type="application/xml")
    
    def _handle_retry(self, message, message_status, retry_count, 
                     temp_message, enable_custom_message, continue_waiting_message, 
                     max_continue_count, crypto_adapter, request):
        """handle retry request"""
        # 检查是否为继续等待消息
        if message_status.get('is_continue_waiting', False):
            return self._handle_continue_waiting_retry(message, message_status, retry_count, 
                                                     continue_waiting_message, max_continue_count, 
                                                     crypto_adapter, request)
        
        # get the completion event
        completion_event = message_status.get('completion_event')
        
        # directly wait for processing to complete or timeout
        # if completed, wait will return True immediately; if not completed, it will wait for the specified time
        is_completed = False
        if completion_event:
            is_completed = completion_event.wait(timeout=RETRY_WAIT_TIMEOUT)
        
        if is_completed or message_status.get('is_completed', False):
            # AI处理完成，返回结果
            response_content = message_status.get('result', '') or "sorry, the processing result is empty"

            if not MessageStatusTracker.mark_result_returned(message):
                return Response("", status=200)
            
            message_status['skip_custom_message'] = True
            retry_completion_event = message_status.get('retry_completion_event')
            if retry_completion_event:
                retry_completion_event.set()
            
            response_xml = ResponseFormatter.format_xml(message, response_content)
            encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
            return Response(encrypted_response, status=200, content_type="application/xml")
        
        # 处理未完成，继续重试策略
        if retry_count < 2:  # 前两次重试返回500状态码
            return Response("", status=500)
        else:  # 最后一次重试
            
            if enable_custom_message:
                # 客服消息模式
                logger.info("启用客服消息模式")
                retry_completion_event = message_status.get('retry_completion_event')
                if retry_completion_event:
                    retry_completion_event.set()
                
                response_xml = ResponseFormatter.format_xml(message, temp_message)
                encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
                return Response(encrypted_response, status=200, content_type="application/xml")
            else:
                # 交互等待模式
                logger.info("启用交互等待模式")
                UserWaitingManager.set_user_waiting(message.from_user, message_status, max_continue_count)
                
                response_xml = ResponseFormatter.format_xml(message, continue_waiting_message)
                encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
                return Response(encrypted_response, status=200, content_type="application/xml")
    
    def _handle_first_request(self, message, message_status, settings, 
                             handler: MessageHandler, enable_custom_message, crypto_adapter: WechatMessageCryptoAdapter, request):
        
        # 检查是否为继续等待请求，如果是则不启动新的AI任务
        if message_status.get('is_continue_waiting', False):
            # 获取继续等待相关配置
            continue_waiting_message = settings.get('continue_waiting_message') or DEFAULT_CONTINUE_MESSAGE
            max_continue_count = int(settings.get('max_continue_count') or DEFAULT_MAX_CONTINUE_COUNT)
            
            # 直接调用继续等待处理逻辑，retry_count=0表示第一次处理
            return self._handle_continue_waiting_retry(
                message, message_status, 0,  # retry_count = 0 for first request
                continue_waiting_message, max_continue_count, 
                crypto_adapter, request
            )
        
        # create the completion event
        completion_event = threading.Event()
        message_status['completion_event'] = completion_event
        
        # create the retry completion event, used to notify the customer message thread
        retry_completion_event = threading.Event()
        message_status['retry_completion_event'] = retry_completion_event
        
        # initialize the customer message skip flag to False
        message_status['skip_custom_message'] = False
        
        # start the asynchronous processing thread
        thread = threading.Thread(
            target=self._async_process_message,
            args=(handler, message, settings, message_status, completion_event),
            daemon=True,
            name=f"Msg-Processor-{message.from_user}"
        )
        
        # record the processing start time and start the thread
        thread.start()
        
        # wait for processing to complete or timeout
        is_completed = completion_event.wait(timeout=DEFAULT_HANDLER_TIMEOUT)
        
        if is_completed:
            # AI处理完成，直接返回结果
            response_content = message_status.get('result', '') or "抱歉，处理结果为空"
            MessageStatusTracker.mark_result_returned(message)
            
            response_xml = ResponseFormatter.format_xml(message, response_content)
            encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
            return Response(encrypted_response, status=200, content_type="application/xml")
        else:
            # 处理超时，启用重试机制
            logger.info("AI处理超时，启用重试机制")
            
            if enable_custom_message:
                async_thread = threading.Thread(
                    target=self._wait_and_send_custom_message,
                    args=(message, message_status, settings, completion_event),
                    daemon=True,
                    name=f"CustomerMsgSender-{message.from_user}"
                )
                async_thread.start()
            
            return Response("", status=500)
    
    def _handle_continue_waiting_retry(self, message, message_status, retry_count, 
                                     continue_waiting_message, max_continue_count, 
                                     crypto_adapter: WechatMessageCryptoAdapter, request):
        """处理继续等待消息的重试"""
        waiting_info = message_status.get('original_waiting_info')
        if not waiting_info:
            logger.warning("继续等待消息缺少原始等待信息")
            UserWaitingManager.clear_user_waiting(message.from_user)
            return Response("", status=500)
        
        # 获取原始AI任务的完成事件
        original_status = waiting_info['original_status']
        completion_event = original_status.get('completion_event')
        
        # 检查原始AI任务是否已完成
        if completion_event and original_status.get('is_completed', False):
            logger.info("继续等待期间AI任务已完成，返回结果")
            UserWaitingManager.clear_user_waiting(message.from_user)
            
            response_content = original_status.get('result', '') or "抱歉，处理结果为空"
            response_xml = ResponseFormatter.format_xml(message, response_content)
            encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
            return Response(encrypted_response, status=200, content_type="application/xml")
        
        # 等待原始AI任务完成
        is_completed = False
        if completion_event:
            is_completed = completion_event.wait(timeout=RETRY_WAIT_TIMEOUT)
        
        if is_completed and original_status.get('is_completed', False):
            # AI任务在等待期间完成了
            logger.info("重试期间AI任务完成")
            UserWaitingManager.clear_user_waiting(message.from_user)
            
            response_content = original_status.get('result', '') or "抱歉，处理结果为空"
            response_xml = ResponseFormatter.format_xml(message, response_content)
            encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
            return Response(encrypted_response, status=200, content_type="application/xml")
        
        # AI任务仍未完成
        if retry_count < 2:  # 前两次重试返回500状态码，触发微信继续重试
            logger.debug(f"继续等待重试: 第{retry_count}次，返回500触发下次重试")
            return Response("", status=500)
        else:  # 最后一次重试
            # 增加continue_count并判断是否达到限制
            UserWaitingManager.handle_continue_request(message.from_user)
            updated_waiting_info = UserWaitingManager.get_waiting_info(message.from_user)
            
            if not updated_waiting_info:
                logger.warning("用户等待状态丢失")
                response_content = "处理时间较长，请稍后重新询问"
                response_xml = ResponseFormatter.format_xml(message, response_content)
                encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
                return Response(encrypted_response, status=200, content_type="application/xml")
            
            # 检查是否达到最大继续次数
            if updated_waiting_info['continue_count'] >= updated_waiting_info['max_continue_count']:
                logger.info("达到最大继续次数，结束等待")
                UserWaitingManager.clear_user_waiting(message.from_user)
                
                response_content = "处理时间较长，请稍后重新询问"
                response_xml = ResponseFormatter.format_xml(message, response_content)
                encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
                return Response(encrypted_response, status=200, content_type="application/xml")
            else:
                # 还可以继续等待
                remaining_count = updated_waiting_info['max_continue_count'] - updated_waiting_info['continue_count']
                if remaining_count > 0:
                    response_content = f"{continue_waiting_message} (剩余{remaining_count}次机会)"
                else:
                    response_content = f"{continue_waiting_message} (最后1次机会)"
                
                # 安全地更新用户等待状态，避免覆盖lock对象
                with UserWaitingManager._waiting_lock:
                    if message.from_user in UserWaitingManager._waiting_users:
                        current_waiting_info = UserWaitingManager._waiting_users[message.from_user]
                        current_waiting_info['start_time'] = time.time()
                        current_waiting_info['expire_time'] = time.time() + 30
                        # 不覆盖整个字典，保持lock对象
                
                logger.info(f"继续等待，剩余{remaining_count}次, response_content: {response_content}")
                response_xml = ResponseFormatter.format_xml(message, response_content)
                encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
                return Response(encrypted_response, status=200, content_type="application/xml")
    

    def _async_process_message(self, handler, message, settings, message_status, completion_event):
        """asynchronous processing message"""
        start_time = time.time()
        
        try:
            # 处理消息
            result = handler.handle(message, self.session, settings)
            
            message_status['result'] = result
            message_status['is_completed'] = True

            MessageStatusTracker.update_status(
                message,
                result=result,
                is_completed=True
            )
        except Exception as e:
            logger.error(f"异步处理消息失败: {str(e)}")
            
            error_msg = f"processing failed: {str(e)}"
            message_status['result'] = error_msg
            message_status['error'] = error_msg
            message_status['is_completed'] = True
            
            MessageStatusTracker.update_status(
                message,
                result=error_msg,
                error=str(e),
                is_completed=True
            )
        finally:
            completion_event.set()
            elapsed = time.time() - start_time
            logger.info(f"消息处理完成，耗时: {elapsed:.2f}秒")
    
    def _wait_and_send_custom_message(self, message, message_status, settings, completion_event):
        """wait for processing to complete and send customer message"""
        try:
            # 等待AI处理完成
            is_completed = completion_event.wait(timeout=300)
            
            if not is_completed:
                logger.warning("AI处理超时(>5分钟)，强制结束")
                MessageStatusTracker.update_status(
                    message.msg_id,
                    result="processing timed out, please try again",
                    is_completed=True,
                    error="processing timed out (>5 minutes)"
                )
                return
            
            # 等待重试流程完成
            retry_completion_event = message_status.get('retry_completion_event')
            if retry_completion_event:
                retry_completed = retry_completion_event.wait(timeout=20)
                if not retry_completed:
                    logger.warning("等待重试流程超时")
            
            # 检查是否需要跳过客服消息
            if message_status.get('skip_custom_message', False):
                return
            
            if not MessageStatusTracker.mark_result_returned(message):
                return
                
            # 获取处理结果并发送客服消息
            content = message_status.get('result', '') or "抱歉，无法获取处理结果"
            
            app_id = settings.get('app_id')
            app_secret = settings.get('app_secret')
            wechat_api_proxy_url = settings.get('wechat_api_proxy_url')
            
            if not app_id or not app_secret:
                logger.error("缺少app_id或app_secret配置")
                return

            sender = WechatCustomMessageSender(app_id, app_secret, wechat_api_proxy_url)
            send_result = sender.send_text_message(
                open_id=message.from_user,
                content=content
            )
            
            if send_result.get('success'):
                logger.info("客服消息发送成功")
            else:
                error_msg = send_result.get('error', 'unknown error')
                logger.error(f"客服消息发送失败: {error_msg}")
        except Exception as e:
            logger.error(f"客服消息处理异常: {str(e)}")
