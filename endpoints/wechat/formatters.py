import time
from .models import WechatMessage

class ResponseFormatter:
    """response formatter"""
    @staticmethod
    def format_xml(message: WechatMessage, content: str) -> str:
        """
        format XML response
        
        params:
            message: wechat message object
            content: reply content
            
        return:
            XML response string conforming to the WeChat public platform specification
        """
        current_timestamp = int(time.time())
        return f"""<xml>
<ToUserName><![CDATA[{message.from_user}]]></ToUserName>
<FromUserName><![CDATA[{message.to_user}]]></FromUserName>
<CreateTime>{current_timestamp}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""

    @staticmethod
    def format_error_xml(from_user: str, to_user: str, content: str) -> str:
        """
        format XML error response
        
        params:
            from_user: sender OpenID
            to_user: receiver ID
            content: error information
            
        return:
            XML error response string
        """
        current_timestamp = int(time.time())
        return f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{current_timestamp}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>""" 