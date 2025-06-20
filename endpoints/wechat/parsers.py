import logging
import xml.etree.ElementTree as ET
from .models import WechatMessage

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

class MessageParser:
    """message parser"""
    @staticmethod
    def parse_xml(raw_data: str) -> WechatMessage:
        """
        parse XML data to WechatMessage object
        
        params:
            raw_data: raw XML data
            
        return:
            WechatMessage object
            
        exception:
            ValueError: when XML parsing fails
        """
        try:
            xml_data = ET.fromstring(raw_data)
            
            # extract common fields
            msg_type = xml_data.find('MsgType').text
            from_user = xml_data.find('FromUserName').text
            to_user = xml_data.find('ToUserName').text
            create_time = xml_data.find('CreateTime').text
            
            # extract message ID (if exists)
            msg_id_elem = xml_data.find('MsgId')
            msg_id = msg_id_elem.text if msg_id_elem is not None else None

            
            # extract specific fields based on different message types
            if msg_type == 'text':
                content = xml_data.find('Content').text
                return WechatMessage(
                    msg_type=msg_type,
                    from_user=from_user,
                    to_user=to_user,
                    create_time=create_time,
                    msg_id=msg_id,
                    content=content
                )
            
            elif msg_type == 'image':
                pic_url = xml_data.find('PicUrl').text
                media_id = xml_data.find('MediaId').text
                return WechatMessage(
                    msg_type=msg_type,
                    from_user=from_user,
                    to_user=to_user,
                    create_time=create_time,
                    msg_id=msg_id,
                    pic_url=pic_url,
                    media_id=media_id
                )
            
            elif msg_type == 'voice':
                media_id = xml_data.find('MediaId').text
                format_elem = xml_data.find('Format')
                format = format_elem.text if format_elem is not None else None
                
                # voice recognition result (may not exist)
                recognition_elem = xml_data.find('Recognition')
                recognition = recognition_elem.text if recognition_elem is not None else None
                
                return WechatMessage(
                    msg_type=msg_type,
                    from_user=from_user,
                    to_user=to_user,
                    create_time=create_time,
                    msg_id=msg_id,
                    media_id=media_id,
                    format=format,
                    recognition=recognition
                )
            
            elif msg_type == 'video' or msg_type == 'shortvideo':
                media_id = xml_data.find('MediaId').text
                thumb_media_id = xml_data.find('ThumbMediaId').text
                return WechatMessage(
                    msg_type=msg_type,
                    from_user=from_user,
                    to_user=to_user,
                    create_time=create_time,
                    msg_id=msg_id,
                    media_id=media_id,
                    thumb_media_id=thumb_media_id
                )
            
            elif msg_type == 'location':
                location_x = xml_data.find('Location_X').text
                location_y = xml_data.find('Location_Y').text
                scale = xml_data.find('Scale').text
                label = xml_data.find('Label').text
                return WechatMessage(
                    msg_type=msg_type,
                    from_user=from_user,
                    to_user=to_user,
                    create_time=create_time,
                    msg_id=msg_id,
                    location_x=location_x,
                    location_y=location_y,
                    scale=scale,
                    label=label
                )
            
            elif msg_type == 'link':
                title = xml_data.find('Title').text
                description = xml_data.find('Description').text
                url = xml_data.find('Url').text
                return WechatMessage(
                    msg_type=msg_type,
                    from_user=from_user,
                    to_user=to_user,
                    create_time=create_time,
                    msg_id=msg_id,
                    title=title,
                    description=description,
                    url=url
                )
            
            elif msg_type == 'event':
                # event type message
                event = xml_data.find('Event').text
                
                # event key (may not exist)
                event_key_elem = xml_data.find('EventKey')
                event_key = event_key_elem.text if event_key_elem is not None else None
                
                # QR code ticket (may not exist, used for scanning QR code with parameters)
                ticket_elem = xml_data.find('Ticket')
                ticket = ticket_elem.text if ticket_elem is not None else None
                
                logger.info(f"parsed event message: event type={event}, event key={event_key}")
                
                return WechatMessage(
                    msg_type=msg_type,
                    from_user=from_user,
                    to_user=to_user,
                    create_time=create_time,
                    msg_id=msg_id,
                    event=event,
                    event_key=event_key,
                    ticket=ticket
                )
            
            else:
                # default construct basic message object
                logger.warning(f"unknown message type: {msg_type}")
                return WechatMessage(
                    msg_type=msg_type,
                    from_user=from_user,
                    to_user=to_user,
                    create_time=create_time,
                    msg_id=msg_id
                )
                
        except Exception as e:
            logger.error(f"failed to parse XML: {str(e)}")
            raise ValueError(f"failed to parse XML: {str(e)}") 