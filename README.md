# Dify微信公众号插件

**作者:** bikeread  
**版本:** 0.0.1  
**类型:** extension  

## 项目概述

Dify微信公众号插件专为自媒体运营者和公众号主理人打造，将AI能力无缝接入您的微信公众号，提供24小时智能客服与内容助手服务。

## 核心价值

1. **智能粉丝互动**: 提供24小时不间断对话服务，提升粉丝活跃度
2. **内容辅助创作**: 为粉丝提供专业问题解答和创意支持
3. **数据收集分析**: 了解粉丝关注点，发现内容机会
4. **降低运营成本**: 自动回复常见问题，减轻人工客服负担

## 主要功能

- **基础支持**: 服务器验证、明文/加密模式、Dify AI智能回复
- **多类型消息**: 支持文本消息，即将支持图片、语音和链接消息
- **会话管理**: 支持对话记忆和历史清除功能
- **技术优化**: 解决微信5秒超时限制，延长至15秒，支持流式响应

## 运营价值

- 提升粉丝活跃度和留存率
- 差异化竞争优势
- 数据驱动内容创作
- 全天候服务能力

## 快速配置

### 微信公众号配置

1. 登录微信公众平台（https://mp.weixin.qq.com/）
2. 进入"设置与开发" -> "基本配置"
3. 在"服务器配置"部分：
   - URL设置为您的Dify插件访问地址，例如：`http://your-domain.com/wechat/input`
   - Token设置一个自定义的安全令牌
   - 选择消息加解密方式
   - 如需加密模式，设置EncodingAESKey

### 插件配置

必选参数：
- `wechat_token`: 与公众号平台配置相同的Token

加密模式参数：
- `encoding_aes_key`: 与公众号平台配置的EncodingAESKey
- `app_id`: 公众号的AppID

客服消息支持：
- `app_secret`: 公众号的AppSecret

可选参数：
- `timeout_message`: 超时时发送的临时响应消息

## 加密模式说明

微信公众平台支持三种消息加解密方式：

1. **明文模式**：消息以明文方式传输，不进行加密。
   - 配置简单，但安全性较低
   - 只需配置`wechat_token`，无需设置`encoding_aes_key`和`app_id`

2. **兼容模式/安全模式**：消息需要加密处理。
   - 安全性更高，需要额外的加解密处理
   - 需要配置：`wechat_token`, `encoding_aes_key`, `app_id`

## 使用方法

1. 完成插件配置，保存并启用
2. 用户发送消息至公众号
3. 系统自动调用AI处理并回复
4. 发送"清除历史聊天记录"可重置对话

## 架构说明

本插件采用模块化设计，主要组件包括：

### 目录结构
```
endpoints/
├── wechat/                    # 微信处理核心模块
│   ├── __init__.py            # 包初始化文件
│   ├── models.py              # 定义WechatMessage消息模型
│   ├── parsers.py             # 定义XML解析器
│   ├── formatters.py          # 定义响应格式化器
│   ├── factory.py             # 定义消息处理器工厂
│   ├── crypto.py              # 微信消息加解密工具
│   ├── retry_tracker.py       # 消息重试跟踪器
│   ├── api/                   # API调用相关
│   │   ├── __init__.py        # API包初始化
│   │   └── custom_message.py  # 客服消息发送器
│   └── handlers/              # 消息处理器
│       ├── __init__.py        # 处理器包初始化
│       ├── base.py            # 定义处理器抽象基类
│       ├── text.py            # 文本消息处理器
│       ├── image.py           # 图片消息处理器
│       ├── voice.py           # 语音消息处理器
│       ├── link.py            # 链接消息处理器
│       └── unsupported.py     # 不支持的消息类型处理器
├── wechat_get.py              # 处理微信服务器验证请求
└── wechat_post.py             # 处理用户发送的消息
```

### 消息处理流程

1. **消息接收**：`wechat_post.py` 接收微信服务器发来的消息
2. **消息解析**：使用 `MessageParser` 解析XML格式的消息
3. **重试检测**：使用 `MessageStatusTracker` 判断是否为重试请求
4. **消息处理**：
   - 首次请求：启动异步线程处理，等待一定时间（默认5.0秒）
   - 重试请求：先等待一段较短时间（默认4.0秒），然后根据处理状态返回适当响应
5. **响应返回**：使用 `ResponseFormatter` 格式化回复，加密后返回
6. **后台处理**：如果处理超时，通过客服消息发送完整回复

### 设计模式

本插件使用了多种设计模式：

1. **策略模式**: 通过`MessageHandler`抽象类定义统一接口，不同消息类型使用不同的实现
2. **工厂模式**: 使用`MessageHandlerFactory`根据消息类型创建相应处理器
3. **适配器模式**: 使用解析器和格式化器转换不同格式的数据
4. **装饰器模式**: 使用装饰器处理消息的加解密
5. **观察者模式**: 使用线程和事件通知机制监控处理完成
6. **异步处理模式**: 使用子线程处理长耗时请求，避免微信超时
7. **单例模式**: `MessageStatusTracker`使用类变量实现单例状态跟踪

## 扩展开发指南

### 添加新的消息类型支持

要添加对新消息类型（如视频、小程序消息等）的支持，按以下步骤操作：

1. 在`handlers`目录下创建新的处理器类，继承`MessageHandler`：

```python
# handlers/video.py
from typing import Dict, Any
from .base import MessageHandler
from ..models import WechatMessage

class VideoMessageHandler(MessageHandler):
    def handle(self, message: WechatMessage, session: Any, app_settings: Dict[str, Any]) -> str:
        # 实现视频消息处理逻辑
        # ...
        return "收到您的视频，正在处理..."
```

2. 在`MessageHandlerFactory`中注册新的处理器：

```python
# 在项目初始化时注册
from endpoints.wechat.factory import MessageHandlerFactory
from endpoints.wechat.handlers.video import VideoMessageHandler

MessageHandlerFactory.register_handler('video', VideoMessageHandler)
```

### 自定义响应格式

要支持更复杂的响应格式（如图文消息），可以扩展`ResponseFormatter`：

```python
@staticmethod
def format_news_xml(message: WechatMessage, articles: list) -> str:
    # 实现图文消息XML格式化
    # ...
```
