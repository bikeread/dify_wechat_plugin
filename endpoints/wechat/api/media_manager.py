import json
import logging
import os
import requests
import time
from typing import Dict, Any, Optional, Union, BinaryIO

from .custom_message import WechatCustomMessageSender

# 导入 logging 和自定义处理器
import logging
from dify_plugin.config.logger_format import plugin_logger_handler

# 使用自定义处理器设置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)


class MediaStrategy:
    """media resource get strategy base class"""
    
    @staticmethod
    def get_media_url(access_token: str, media_id: str, api_base_url: str = "api.weixin.qq.com") -> str:
        """get media resource url base method"""
        raise NotImplementedError("subclass must implement this method")
        
    @staticmethod
    def process_response(response: requests.Response) -> Dict[str, Any]:
        """process response result base method"""
        raise NotImplementedError("subclass must implement this method")


class NormalMediaStrategy(MediaStrategy):
    """normal temporary media resource get strategy"""
    
    @staticmethod
    def get_media_url(access_token: str, media_id: str, api_base_url: str = "api.weixin.qq.com") -> str:
        return f"https://{api_base_url}/cgi-bin/media/get?access_token={access_token}&media_id={media_id}"
    
    @staticmethod
    def process_response(response: requests.Response) -> Dict[str, Any]:
        # check http status code
        if response.status_code != 200:
            return {
                'success': False,
                'error': f"get media file failed: HTTP status code {response.status_code}",
                'status_code': response.status_code
            }
        
        # check if it can be parsed as JSON (wechat api usually returns JSON when an error occurs)
        try:
            result = response.json()
            # check if it contains errcode field, if it does and is not 0, it means an exception
            if 'errcode' in result and result['errcode'] != 0:
                return {
                    'success': False,
                    'error': result.get('errmsg', 'unknown error'),
                    'errcode': result.get('errcode'),
                    'raw_response': result
                }
                
            # check if it is a video url response (successful video response contains video_url field)
            if 'video_url' in result:
                return {
                    'success': True,
                    'media_type': 'video',
                    'video_url': result.get('video_url', ''),
                    'raw_response': result
                }
        except ValueError:
            # if it cannot be parsed as JSON, it means it is a binary media file
            pass
            
        # process binary media file
        filename = ""
        content_disposition = response.headers.get('Content-disposition', '')
        if 'filename=' in content_disposition:
            filename = content_disposition.split('filename=')[1].strip('"')
        
        return {
            'success': True,
            'media_type': response.headers.get('Content-Type', ''),
            'filename': filename,
            'content': response.content
        }


class JssdkMediaStrategy(MediaStrategy):
    """jssdk high definition voice material get strategy"""
    
    @staticmethod
    def get_media_url(access_token: str, media_id: str, api_base_url: str = "api.weixin.qq.com") -> str:
        return f"https://{api_base_url}/cgi-bin/media/get/jssdk?access_token={access_token}&media_id={media_id}"
    
    @staticmethod
    def process_response(response: requests.Response) -> Dict[str, Any]:
        # check http status code
        if response.status_code != 200:
            return {
                'success': False,
                'error': f"get high definition voice file failed: HTTP status code {response.status_code}",
                'status_code': response.status_code
            }
        
        # check if it can be parsed as JSON (wechat api usually returns JSON when an error occurs)
        try:
            result = response.json()
            # check if it contains errcode field, if it does and is not 0, it means an exception
            if 'errcode' in result and result['errcode'] != 0:
                return {
                    'success': False,
                    'error': result.get('errmsg', 'unknown error'),
                    'errcode': result.get('errcode'),
                    'raw_response': result
                }
        except ValueError:
            # if it cannot be parsed as JSON, it means it is a binary media file
            pass
            
        # process binary media file
        filename = ""
        content_disposition = response.headers.get('Content-disposition', '')
        if 'filename=' in content_disposition:
            filename = content_disposition.split('filename=')[1].strip('"')
        
        return {
            'success': True,
            'media_type': 'voice/speex',
            'filename': filename,
            'content': response.content
        }


class MediaStrategyFactory:
    """media strategy factory"""
    
    @staticmethod
    def create_strategy(media_type: str = 'normal') -> MediaStrategy:
        """
        create media get strategy
        
        params:
            media_type: media type, optional values: 'normal'(normal temporary media), 'jssdk'(high definition voice material)
            
        return:
            corresponding media get strategy object
        """
        strategies = {
            'normal': NormalMediaStrategy,
            'jssdk': JssdkMediaStrategy
        }
        
        return strategies.get(media_type, NormalMediaStrategy)()


class WechatMediaManager:
    """wechat media resource manager"""
    
    def __init__(self, app_id: str, app_secret: str, api_base_url: str = None, storage=None):
        """
        initialize media resource manager
        
        params:
            app_id: wechat public account app id
            app_secret: wechat public account app secret
            api_base_url: wechat api base url, default is api.weixin.qq.com
            storage: storage object, used to cache access token
        """
        self.api_base_url = api_base_url or "api.weixin.qq.com"
        self.message_sender = WechatCustomMessageSender(app_id, app_secret, api_base_url)
    
    def get_media(self, media_id: str, media_type: str = 'normal') -> Dict[str, Any]:
        """
        get temporary media
        
        params:
            media_id: media file id
            media_type: media type, optional values: 'normal'(normal temporary media), 'jssdk'(high definition voice material)
            
        return:
            dictionary containing media file content or URL
            
        exception:
            Exception: when get failed
        """
        try:
            # get access token
            access_token = self.message_sender._get_access_token()
            
            # create corresponding strategy using factory
            strategy = MediaStrategyFactory.create_strategy(media_type)
            
            # build request url
            url = strategy.get_media_url(access_token, media_id, self.api_base_url)
            
            # send request
            response = requests.get(url, timeout=30, stream=True)
            
            # process response
            return strategy.process_response(response)
            
        except Exception as e:
            logger.error(f"get media file failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def download_media(self, media_id: str, save_path: str, media_type: str = 'normal') -> Dict[str, Any]:
        """
        download temporary media and save to file
        
        params:
            media_id: media file id
            save_path: save path, if it is a directory, use the original file name, otherwise use the specified file name
            media_type: media type, optional values: 'normal'(normal temporary media), 'jssdk'(high definition voice material)
            
        return:
            download result
            
        exception:
            Exception: when download failed
        """
        try:
            # get media file
            result = self.get_media(media_id, media_type)
            
            if not result['success']:
                return result
            
            # if it is a video URL, return URL without downloading
            if result.get('media_type') == 'video':
                return {
                    'success': True,
                    'video_url': result.get('video_url', ''),
                    'saved': False,
                    'message': 'video type returns URL, no file downloaded'
                }
            
            # determine save file path
            if os.path.isdir(save_path):
                # if it is a directory, use the original file name
                filename = result.get('filename', f"{media_id}.bin")
                file_path = os.path.join(save_path, filename)
            else:
                # use the specified file path directly
                file_path = save_path
            
            # save file
            with open(file_path, 'wb') as f:
                f.write(result.get('content', b''))
            
            return {
                'success': True,
                'saved': True,
                'file_path': file_path,
                'media_type': result.get('media_type', '')
            }
            
        except Exception as e:
            logger.error(f"download media file failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }