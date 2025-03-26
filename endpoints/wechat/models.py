from typing import Optional, Dict, Any, List

class WechatMessage:
    """wechat message entity class"""
    def __init__(self, 
                 msg_type: str, 
                 from_user: str, 
                 to_user: str, 
                 create_time: str, 
                 msg_id: Optional[str] = None,
                 content: Optional[str] = None,
                 pic_url: Optional[str] = None,
                 media_id: Optional[str] = None,
                 format: Optional[str] = None,
                 recognition: Optional[str] = None,
                 thumb_media_id: Optional[str] = None,
                 location_x: Optional[str] = None,
                 location_y: Optional[str] = None,
                 scale: Optional[str] = None,
                 label: Optional[str] = None,
                 title: Optional[str] = None,
                 description: Optional[str] = None,
                 url: Optional[str] = None,
                 # event related attributes
                 event: Optional[str] = None,
                 event_key: Optional[str] = None,
                 ticket: Optional[str] = None):
        """
        initialize the wechat message object
        
        params:
            msg_type: message type (e.g. 'text', 'image', 'voice', 'link', 'event' etc.)
            from_user: sender's OpenID
            to_user: receiver's ID (original ID of the public account)
            create_time: message creation time
            msg_id: message ID
            content: text message content (valid for text messages)
            pic_url: image link (valid for image messages)
            media_id: media ID of image or voice
            format: voice format (valid for voice messages)
            recognition: voice recognition result (valid for voice messages)
            thumb_media_id: media ID of video thumbnail (valid for video messages)
            location_x: latitude
            location_y: longitude
            scale: map zoom size
            label: location information
            title: message title (valid for link messages)
            description: message description (valid for link messages)
            url: message link (valid for link messages)
            event: event type (valid for event messages, e.g. 'subscribe', 'CLICK' etc.)
            event_key: event key value (valid for menu click events)
            ticket: ticket of QR code (valid for scanning QR code with parameters)
        """
        self.msg_type = msg_type
        self.from_user = from_user
        self.to_user = to_user
        self.create_time = create_time
        self.msg_id = msg_id
        
        # text message specific attributes
        self.content = content
        
        # image message specific attributes
        self.pic_url = pic_url
        self.media_id = media_id
        
        # voice message specific attributes
        self.format = format
        self.recognition = recognition
        
        # video message specific attributes
        self.thumb_media_id = thumb_media_id
        
        # location message specific attributes
        self.location_x = location_x
        self.location_y = location_y
        self.scale = scale
        self.label = label
        
        # link message specific attributes
        self.title = title
        self.description = description
        self.url = url
        
        # event message specific attributes
        self.event = event
        self.event_key = event_key
        self.ticket = ticket
    
    def __str__(self) -> str:
        """return the string representation of the message"""
        if self.msg_type == 'text':
            return f"WechatMessage(type={self.msg_type}, from={self.from_user}, content={self.content})"
        elif self.msg_type == 'image':
            return f"WechatMessage(type={self.msg_type}, from={self.from_user}, pic_url={self.pic_url})"
        elif self.msg_type == 'voice':
            return f"WechatMessage(type={self.msg_type}, from={self.from_user}, format={self.format})"
        elif self.msg_type == 'link':
            return f"WechatMessage(type={self.msg_type}, from={self.from_user}, title={self.title}, url={self.url})"
        elif self.msg_type == 'event':
            return f"WechatMessage(type={self.msg_type}, from={self.from_user}, event={self.event}, event_key={self.event_key})"
        else:
            return f"WechatMessage(type={self.msg_type}, from={self.from_user})" 