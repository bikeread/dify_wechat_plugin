import logging
import threading
import time
import json
from typing import Mapping, Optional, Dict, Any
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

# get the logger for the current module
logger = logging.getLogger(__name__)

# default timeout and response settings
DEFAULT_HANDLER_TIMEOUT = 5.0  # default timeout time 5.0 seconds, fixed value
DEFAULT_TEMP_RESPONSE = "内容生成耗时较长，请稍等..."  # default temporary response message
# retry waiting time is half of the normal timeout time
RETRY_WAIT_TIMEOUT = DEFAULT_HANDLER_TIMEOUT * 0.8  # use a shorter waiting time for retries
# clear history identifier message
CLEAR_HISTORY_MESSAGE = "/clear"


class WechatPost(Endpoint):
    """wechat public account message processing endpoint"""
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """handle wechat request"""
        # record request information
        logger.info("===== wechat request information =====")
        logger.debug(f"request method: {r.method}, URL: {r.url}")
        logger.debug(f"request headers: {dict(r.headers)}")
        
        # record query parameters and form data (if any)
        if r.args:
            logger.debug(f"query parameters: {dict(r.args)}")

        logger.info("application configuration: %s", settings)

        # 1. get the temporary response message from the configuration
        temp_response_message = settings.get('timeout_message', DEFAULT_TEMP_RESPONSE)
        
        try:
            # 2. create the encryption adapter
            crypto_adapter = WechatMessageCryptoAdapter(settings)
            
            # 3. decrypt the message
            try:
                decrypted_data = crypto_adapter.decrypt_message(r)
                logger.debug(f"decrypted data: {decrypted_data}")
            except Exception as e:
                logger.error(f"failed to decrypt message: {str(e)}")
                return Response('decryption failed', status=400)
                
            # 4. parse the message content
            message = MessageParser.parse_xml(decrypted_data)
            # create the handler and call the clear cache method
            handler = MessageHandlerFactory.get_handler(message.msg_type)
            # if the clear history instruction is received
            if message.content == CLEAR_HISTORY_MESSAGE:
                success = handler.clear_cache(self.session, message.from_user)
                
                # return the clear result
                result_message = "history chat records have been cleared" if success else "failed to clear history records, please try again later"
                logger.info(f"clear history operation: {result_message}")
                
                # return the response
                response_xml = ResponseFormatter.format_xml(message, result_message)
                encrypted_response = crypto_adapter.encrypt_message(response_xml, r)
                return Response(encrypted_response, status=200, content_type="application/xml")

            # 5. use MessageStatusTracker to track the message status
            # directly pass the message object, let the tracker decide which identifier to use
            message_status = MessageStatusTracker.track_message(message)
            retry_count = message_status.get('retry_count', 0)
            
            # initialize the result returned flag
            message_status['result_returned'] = False
            
            # 6. handle the retry request
            if retry_count > 0:
                logger.info(f"detected retry request, current retry count: {retry_count}")
                return self._handle_retry(message, message_status, retry_count, 
                                        temp_response_message, crypto_adapter, r)
            
            # 7. handle the first request
            return self._handle_first_request(message, message_status, settings, 
                                            handler, crypto_adapter, r)
        except Exception as e:
            logger.error(f"failed to handle request: {str(e)}")
            return Response("", status=200, content_type="application/xml")
    
    def _handle_retry(self, message, message_status, retry_count, 
                     temp_message, crypto_adapter, request):
        """handle retry request"""
        # get the completion event
        completion_event = message_status.get('completion_event')
        
        # directly wait for processing to complete or timeout
        # if completed, wait will return True immediately; if not completed, it will wait for the specified time
        is_completed = False
        if completion_event:
            is_completed = completion_event.wait(timeout=RETRY_WAIT_TIMEOUT)
        
        if is_completed or message_status.get('is_completed', False):
            # the processing has been completed, return the result
            logger.debug(f"retry request: processing completed or completed during waiting, return the result directly")
            response_content = message_status.get('result', '') or "sorry, the processing result is empty"

            # use the atomic operation to mark the result as returned
            if not MessageStatusTracker.mark_result_returned(message):
                logger.debug(f"retry request: the result has been returned by other threads, skip processing")
                return Response("", status=200)
            
            # HTTP returned the complete result, explicitly set the skip_custom_message flag
            # this is more explicit than only setting retry_completion_event
            message_status['skip_custom_message'] = True
            
            # set the retry completion event, also notify the customer message thread
            retry_completion_event = message_status.get('retry_completion_event')
            if retry_completion_event:
                logger.debug(f"retry request: HTTP returned the complete result, notify the customer message thread to skip sending")
                retry_completion_event.set()
            
            # format and return the response
            response_xml = ResponseFormatter.format_xml(message, response_content)
            encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
            return Response(encrypted_response, status=200, content_type="application/xml")
        
        # still not completed after waiting, continue the original retry strategy
        logger.debug(f"retry request: processing not completed, {retry_count}th retry")
        if retry_count < 2:  # the first two retries return 500 status code
            logger.debug(f"retry request: return 500 status code to trigger subsequent retries")
            return Response("", status=500)
        else:  # the last retry, return the temporary message
            logger.info(f"retry request: the last retry, return the temporary message")
            
            # get the retry completion event and set it, notify the customer message thread to start sending
            # but do not set skip_custom_message, indicating that the full result needs to be sent through the customer message
            retry_completion_event = message_status.get('retry_completion_event')
            if retry_completion_event:
                logger.debug(f"retry request: the last retry completed, notify the customer message thread to start sending")
                retry_completion_event.set()
            
            response_xml = ResponseFormatter.format_xml(message, temp_message)
            encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
            return Response(encrypted_response, status=200, content_type="application/xml")
    
    def _handle_first_request(self, message, message_status, settings, 
                             handler: MessageHandler, crypto_adapter, request):
        
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
            # the processing has been completed, return the result directly
            response_content = message_status.get('result', '') or "抱歉，处理结果为空"

            # the first request directly marks the result as returned, there is no competition
            MessageStatusTracker.mark_result_returned(message)
            
            # format and return the response
            response_xml = ResponseFormatter.format_xml(message, response_content)
            encrypted_response = crypto_adapter.encrypt_message(response_xml, request)
            return Response(encrypted_response, status=200, content_type="application/xml")
        else:
            # the processing has timed out, send the temporary response and continue the asynchronous processing
            logger.info(f"first request: processing timed out, switched to asynchronous processing")
            
            # start the asynchronous sending customer message thread
            async_thread = threading.Thread(
                target=self._wait_and_send_custom_message,
                args=(message, message_status, settings, completion_event),
                daemon=True,
                name=f"CustomerMsgSender-{message.from_user}"
            )
            async_thread.start()
            
            return Response("", status=500)
    
    def _async_process_message(self, handler, message, settings, message_status, completion_event):
        """asynchronous processing message"""
        start_time = time.time()
        
        try:
            logger.debug(f"asynchronous processing: start processing message {message.msg_type}-{message.from_user}")
            
            # use the processor to process the message
            result = handler.handle(message, self.session, settings)
            
            # print the full result (debug level)
            logger.debug(f"asynchronous processing: get the full result:\n{result}")
            
            # update the status
            message_status['result'] = result
            message_status['is_completed'] = True

            # update the tracker
            MessageStatusTracker.update_status(
                message,
                result=result,
                is_completed=True
            )
        except Exception as e:
            logger.error(f"asynchronous processing: error occurred while processing message: {str(e)}")
            
            # update the error status
            error_msg = f"processing failed: {str(e)}"
            message_status['result'] = error_msg
            message_status['error'] = error_msg
            message_status['is_completed'] = True
            
            # update the tracker
            MessageStatusTracker.update_status(
                message,
                result=error_msg,
                error=str(e),
                is_completed=True
            )
        finally:
            # set the completion event
            completion_event.set()
            
            # record the processing time
            elapsed = time.time() - start_time
            logger.info(f"asynchronous processing: message {message.msg_id} processed, time elapsed: {elapsed:.2f} seconds")
    
    def _wait_and_send_custom_message(self, message, message_status, settings, completion_event):
        """wait for processing to complete and send customer message"""
        try:
            # first wait for processing to complete (up to 5 minutes)
            is_completed = completion_event.wait(timeout=300)
            
            if not is_completed:
                logger.warning(f"customer message: waiting for processing to complete (>5 minutes), force end waiting")
                MessageStatusTracker.update_status(
                    message.msg_id,
                    result="processing timed out, please try again",
                    is_completed=True,
                    error="processing timed out (>5 minutes)"
                )
                return
            
            # wait for the retry process to complete (use event instead of polling)
            retry_completion_event = message_status.get('retry_completion_event')
            if retry_completion_event:
                logger.debug(f"customer message: waiting for the retry process to complete...")
                # set a reasonable timeout, for example 20 seconds
                retry_completed = retry_completion_event.wait(timeout=20)
                
                if not retry_completed:
                    logger.warning(f"customer message: waiting for the retry process to complete (>20 seconds)")
                else:
                    logger.debug(f"customer message: the retry process has been completed")
            
            # check if the customer message should be skipped
            if message_status.get('skip_custom_message', False):
                logger.debug(f"customer message: HTTP returned the complete result, skip sending")
                return
            
            # use the atomic operation to mark the result as returned, if the marking fails, it means the result has been returned by HTTP
            if not MessageStatusTracker.mark_result_returned(message):
                logger.debug(f"customer message: the result has been returned by other means, skip sending")
                return
                
            # get the processing result
            content = message_status.get('result', '') or "抱歉，无法获取处理结果"
            
            # print the full content (debug level)
            logger.debug(f"customer message: full content:\n{content}")
            
            # check if the configuration has the parameters required for customer message
            app_id = settings.get('app_id')
            app_secret = settings.get('app_secret')
            
            if not app_id or not app_secret:
                logger.error("customer message: missing app_id or app_secret configuration")
                return

            # initialize the customer message sender and send the message
            sender = WechatCustomMessageSender(app_id, app_secret)
            logger.debug(f"customer message: sending to user {message.from_user}, content length: {len(content)}")
            
            send_result = sender.send_text_message(
                open_id=message.from_user,
                content=content
            )
            
            if send_result.get('success'):
                logger.info("customer message: sent successfully")
            else:
                error_msg = send_result.get('error', 'unknown error')
                logger.error(f"customer message: sending failed: {error_msg}")
        except Exception as e:
            logger.error(f"customer message: error occurred during processing: {str(e)}")
