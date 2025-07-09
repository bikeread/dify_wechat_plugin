from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Optional
import time
import threading

from ..models import WechatMessage

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

# define timeout constants
STREAM_CHUNK_TIMEOUT = 30  # maximum wait time for a single chunk (seconds)
MAX_TOTAL_STREAM_TIME = 240  # maximum total stream processing time (seconds)


class MessageHandler(ABC):
    """message handler abstract base class"""
    def __init__(self):
        """initialize handler"""
        self.initial_conversation_id = None
        self.new_conversation_id = None

    @abstractmethod
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        """
        handle message and return reply content
        
        params:
            message: wechat message object to handle
            session: current session object for accessing storage and AI interface
            app_settings: application settings dictionary
            
        return:
            processed reply content string
        """
        pass

    def clear_cache(self, session: Any, user_id: str, app_id: str) -> bool:
        """
        clear cache for specified user
        
        params:
            session: current session object for accessing storage
            user_id: user identifier (e.g. wechat user open id)
            
        return:
            bool: whether cache is cleared successfully
        """
        try:
            # construct storage key
            storage_key = self.get_storage_key(user_id, app_id)
            logger.info(f"preparing to clear cache for user '{user_id}', storage key: '{storage_key}'")

            # delete session data
            session.storage.delete(storage_key)
            logger.info(f"successfully cleared cache for user '{user_id}'")
            return True
        except Exception as e:
            logger.error(f"failed to clear cache for user '{user_id}': {str(e)}")
            return True

    def get_storage_key(self, user_id: str, app_id: str) -> str:
        """
        get storage key for user session
        
        params:
            user_id: user identifier (e.g. wechat user open id)
            
        return:
            str: storage key
        """
        return f"wechat_conv_{user_id}_{app_id}"

    def _get_conversation_id(self, session: Any, storage_key: str) -> Optional[str]:
        """
        get stored conversation id
        
        params:
            session: current session object for accessing storage
            storage_key: storage key
            
        return:
            Optional[str]: conversation id, return None if not found
        """
        try:
            stored_data = session.storage.get(storage_key)
            if stored_data:
                conversation_id = stored_data.decode('utf-8')
                logger.debug(f"using existing conversation id: {conversation_id[:8]}...")
                return conversation_id
            logger.debug(f"no stored conversation id found (key: {storage_key}), will create new conversation")
            return None
        except Exception as e:
            logger.warning(f"failed to get stored conversation id: {str(e)}")
            return None

    def _invoke_ai(self, session: Any, app: Dict[str, Any], content: str, conversation_id: Optional[str], inputs: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None) -> Any:
        """invoke AI interface, get streaming response generator"""
        # record initial conversation id
        self.initial_conversation_id = conversation_id
        self.new_conversation_id = None

        # prepare invoke parameters
        invoke_params = {
            "app_id": app.get("app").get("app_id"),
            "query": content,
            "inputs": inputs or {},
            "response_mode": "streaming"
        }

        # only add valid conversation id to parameters when it is obtained
        if conversation_id:
            invoke_params["conversation_id"] = conversation_id

        logger.debug(f"invoke Dify API, parameters: {invoke_params}")
        try:
            try:
                response_generator = session.app.chat.invoke(**invoke_params)
            except Exception as e:
                logger.error(f"failed to invoke Dify API: {str(e)}")
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    logger.error(f"API error response: {e.response.text}")
                raise

            # get first response chunk
            first_chunk = next(response_generator)

            # check if it contains conversation_id
            if isinstance(first_chunk, dict) and 'conversation_id' in first_chunk:
                self.new_conversation_id = first_chunk['conversation_id']
                logger.debug(f"got new conversation id: {self.new_conversation_id[:8]}...")
                
                # immediately save new conversation id
                if session and hasattr(session, 'storage') and user_id and self.new_conversation_id != self.initial_conversation_id:
                    try:
                        storage_key = self.get_storage_key(user_id, app.get("app").get("app_id"))
                        session.storage.set(storage_key, self.new_conversation_id.encode('utf-8'))
                        logger.info(f"immediately saved new conversation id for user '{user_id}'")
                    except Exception as e:
                        logger.error(f"failed to immediately save conversation id: {str(e)}")

            # create a new generator, first return the first chunk, then return the rest of the original generator
            def combined_generator():
                yield first_chunk
                yield from response_generator

            return combined_generator()
        except Exception as e:
            logger.error(f"failed to invoke AI interface: {str(e)}")
            return (x for x in [])

    def _process_ai_response(self, response_generator: Any) -> str:
        """process AI interface streaming response"""
        if not response_generator:
            return "system processing, please try again later"

        start_time = time.time()
        chunk_count = 0
        full_content = ""

        try:
            # iterate streaming response
            for chunk in self._safe_iterate(response_generator):
                chunk_count += 1

                # check if chunk is valid
                if not isinstance(chunk, dict):
                    continue

                # process message content
                if 'answer' in chunk:
                    full_content += chunk.get('answer', '')

                # check message end event
                if chunk.get('event') == 'message_end':
                    message_end_received = True
                    break  # receive end event and exit loop directly

            # calculate total processing time
            total_time = time.time() - start_time

            logger.info(f"streaming response processed, {chunk_count} chunks, total time: {total_time:.2f} seconds")

            # return full reply content
            return full_content or "AI did not give a reply"
        except Exception as e:
            logger.error(f"error processing streaming response: {str(e)}")
            return f"error processing AI reply: {str(e)}"

    def _safe_iterate(self, response_generator):
        """safely iterate generator, add timeout protection"""
        done = False

        while not done:
            try:
                # use timeout thread to prevent infinite blocking
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

                # create thread to get next chunk
                thread = threading.Thread(target=get_next_chunk)
                thread.daemon = True
                thread.start()

                # wait for thread to complete or timeout
                thread.join(timeout=STREAM_CHUNK_TIMEOUT)

                # check if thread is still running (timeout)
                if thread.is_alive():
                    logger.warning(f"streaming response chunk timeout (waited {STREAM_CHUNK_TIMEOUT} seconds)")
                    done = True
                    break

                # check if iteration is done
                if iteration_done[0]:
                    done = True
                    break

                # check if there is an exception
                if exception_caught[0]:
                    logger.error(f"error iterating streaming response: {exception_caught[0]}")
                    if hasattr(exception_caught[0], 'response') and hasattr(exception_caught[0].response, 'text'):
                        logger.error(f"API error response: {exception_caught[0].response.text}")
                    raise exception_caught[0]

                # return the chunk received
                yield chunk_received[0]

            except Exception as e:
                logger.error(f"error iterating streaming response: {str(e)}")
                done = True
                break

    def save_conversation_id(self, session: Any, user_id: str, app_id: str) -> None:
        """save conversation id"""
        if self.new_conversation_id and self.new_conversation_id != self.initial_conversation_id:
            storage_key = self.get_storage_key(user_id, app_id)
            try:
                session.storage.set(storage_key, self.new_conversation_id.encode('utf-8'))
                logger.info(f"saved new conversation id for user '{user_id}'")
            except Exception as e:
                logger.error(f"failed to save conversation id: {str(e)}")
