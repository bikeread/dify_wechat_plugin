import json
import logging
import requests
import time
from typing import Dict, Any, Optional

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

class WechatCustomMessageSender:
    """wechat custom message sender"""
    
    TOKEN_CACHE = {}  # for caching access token
    
    def __init__(self, app_id: str, app_secret: str, api_base_url: str = None):
        """
        initialize custom message sender
        
        params:
            app_id: wechat public account app id
            app_secret: wechat public account app secret
            api_base_url: wechat api base url, default is api.weixin.qq.com
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.api_base_url = api_base_url or "api.weixin.qq.com"
    
    def _get_access_token(self) -> str:
        """
        get wechat api access token
        
        return:
            valid access_token string
        
        exception:
            Exception: when get token failed
        """
        # check if there is a valid token in cache
        cache_key = f"{self.app_id}_{self.app_secret}"
        if cache_key in self.TOKEN_CACHE:
            token_info = self.TOKEN_CACHE[cache_key]
            # check if the token is expired (refresh 5 minutes before expiration)
            if token_info['expires_at'] > time.time() + 300:
                return token_info['token']
        
        # request new access token
        url = f"https://{self.api_base_url}/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        
        try:
            response = requests.get(url, timeout=10)
            result = response.json()
            
            if 'access_token' in result:
                # calculate expiration time (token valid period is usually 7200 seconds)
                expires_at = time.time() + result.get('expires_in', 7200)
                # save to cache
                self.TOKEN_CACHE[cache_key] = {
                    'token': result['access_token'],
                    'expires_at': expires_at
                }
                return result['access_token']
            else:
                error_msg = f"get access token failed: {result.get('errmsg', 'unknown error')}"
                logger.error(error_msg)
                raise Exception(error_msg)
        
        except Exception as e:
            logger.error(f"request access token error: {str(e)}")
            raise
    
    def send_text_message(self, open_id: str, content: str) -> Dict[str, Any]:
        """
        send text custom message
        
        params:
            open_id: user open id
            content: text message content
            
        return:
            API response result
            
        exception:
            Exception: when send failed
        """
        try:
            # get access token
            access_token = self._get_access_token()
            
            # build request url
            url = f"https://{self.api_base_url}/cgi-bin/message/custom/send?access_token={access_token}"
            
            # build request data
            data = {
                "touser": open_id,
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
            
            # send request
            response = requests.post(
                url=url,
                data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            # parse response
            result = response.json()
            
            if result.get('errcode', 0) != 0:
                error_msg = f"send custom message failed: {result.get('errmsg', 'unknown error')}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'raw_response': result
                }
            
            return {
                'success': True,
                'raw_response': result
            }
            
        except Exception as e:
            logger.error(f"send custom message error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }