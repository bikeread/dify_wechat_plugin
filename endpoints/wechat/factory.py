from typing import Dict, Type

from .handlers.base import MessageHandler
from .handlers.text import TextMessageHandler
from .handlers.unsupported import UnsupportedMessageHandler
from .handlers.image import ImageMessageHandler
from .handlers.voice import VoiceMessageHandler
from .handlers.link import LinkMessageHandler
from .handlers.event import EventMessageHandler

class MessageHandlerFactory:
    """message handler factory"""
    _handlers: Dict[str, Type[MessageHandler]] = {
        'text': TextMessageHandler,
        'image': ImageMessageHandler,
        'voice': VoiceMessageHandler,
        'link': LinkMessageHandler,
        'event': EventMessageHandler,
        'default': UnsupportedMessageHandler
    }
    
    @classmethod
    def get_handler(cls, msg_type: str) -> MessageHandler:
        """
        get the message handler for the corresponding type
        
        params:
            msg_type: message type
            
        return:
            the instance of the message handler for the corresponding type
        """
        handler_class = cls._handlers.get(msg_type, cls._handlers['default'])
        return handler_class()
    
    @classmethod
    def register_handler(cls, msg_type: str, handler_class: Type[MessageHandler]) -> None:
        """
        register a new message handler
        
        params:
            msg_type: message type
            handler_class: the corresponding handler class
        """
        cls._handlers[msg_type] = handler_class 