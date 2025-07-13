# Dify WeChat Official Account Plugin

⭐ **If this plugin helps you, please give it a star!** ⭐

**Language:** [English](README.md) | [中文](README_zh.md)

**Author:** bikeread  
**Version:** 6  
**Type:** extension  
**GitHub:** [Repository](https://github.com/bikeread/dify_wechat_plugin) | [Issues](https://github.com/bikeread/dify_wechat_plugin/issues)

## 📝 What's New in v0.0.5

🎉 **Major updates from v0.0.4 to v0.0.5:**

1. **🔧 Plugin Installation Fix** - Fixed plugin installation errors to ensure smooth setup process

### Previous Updates (v0.0.4)

**Major updates from v0.0.3 to v0.0.4:**

1. **🌐 WeChat API Proxy Support** - Configure custom WeChat API proxy to bypass whitelist restrictions
2. **⏱️ Configurable Retry Timeout** - Adjust retry wait timeout ratio (default 0.7) for better response timing
3. **🔥 Interactive Waiting Mode** - When customer service messages are disabled and AI response takes too long, users can reply "1" to extend waiting time with configurable retry limits

---

> 🚀 **Love this project?** Show your support by giving it a ⭐ on GitHub!  
> 💡 **Found it useful?** Help others discover it by starring the repository!  
> 🎯 **Want updates?** Star and watch to get notified of new features!

## Overview

The Dify WeChat Official Account Plugin is designed for content creators and public account owners who want to integrate AI capabilities into their WeChat Official Accounts. It provides 24/7 intelligent customer service and content assistance.

## Quick Setup Guide

### Step 1: Configure the Plugin

1. After installing the plugin, create a new endpoint
2. Configure the following settings:

#### Required Settings
   - **Endpoint Name**: Any name you prefer
   - **APP**: Select the Dify application that will handle user messages
   - **AppID**: Your Official Account's AppID
   - **WeChat Token**: Copy from your WeChat Official Account platform

#### Encryption Mode Settings (Optional)
   - **EncodingAESKey**: Copy from your WeChat Official Account platform (leave empty if not configured)
   - **AppSecret**: Your Official Account's AppSecret

#### Timeout & Response Settings (Optional)
   - **Timeout Message**: A message to show when response takes longer than 15 seconds (default: "内容生成耗时较长，请稍等...")
   - **Retry Wait Timeout Ratio**: Retry wait timeout ratio between 0.1-1.0 (default: 0.7)

#### Customer Service Message Mode (Optional)
   - **Enable Custom Message**: Enable customer service messages (requires customer service message permission, default: false)

#### Interactive Waiting Mode (Optional, only effective when custom message is disabled)
   - **Continue Waiting Message**: Continue waiting prompt message (default: "生成答复中，继续等待请回复1")
   - **Max Continue Count**: Maximum continue waiting count (default: 2)

#### Network Settings (Optional)
   - **WeChat API Proxy URL**: Custom WeChat API proxy address (default: api.weixin.qq.com, do not include https://, http is not supported)

> **Note**: The timeout message is important because WeChat requires a response within 15 seconds. If your AI application takes longer to generate a complete response:
> - The timeout message will be sent as an immediate response
> - If AppID and AppSecret are configured, the complete AI response will be sent via WeChat's customer service message API
> - Please ensure your Official Account has permission to send customer service messages

### Step 2: Configure WeChat Official Account

1. Log in to WeChat Official Account Platform (https://mp.weixin.qq.com/)
2. Go to "Settings & Development" -> "Basic Settings"
3. Under "Server Configuration":
   - Copy one of the two endpoint URLs from your plugin configuration
   - Paste it into the "Server URL" field
   - Set the same Token as configured in your plugin
   - Choose message encryption method (Plain Text or Secure Mode)
   - If using Secure Mode, set the same EncodingAESKey as in your plugin
4. Click "Submit" to save the configuration

![Configuration Example](img.png)

### Step 3: Verify Configuration

1. After saving both plugin and WeChat configurations
2. Send a test message to your Official Account
3. If you receive an AI response, the configuration is successful

> 🎉 **Success!** If everything works perfectly, consider giving this project a ⭐ to help others find it!

## Advanced Usage

### Supported Message Types

This plugin supports multiple types of messages that your users can send to your WeChat Official Account:

#### 1. Text Messages
- Users can send regular text messages
- Relevant input parameters:
  ```
  msgId: Unique message ID
  msgType: Message type ("text")
  fromUser: Sender's OpenID
  createTime: Message creation timestamp
  content: The text message content
  ```

#### 2. Image Messages
- Users can send image content
- The system provides image URL to AI for processing
- Relevant input parameters:
  ```
  msgId: Unique message ID
  msgType: Message type ("image")
  fromUser: Sender's OpenID
  createTime: Message creation timestamp
  picUrl: URL of the image sent by user
  ```

#### 3. Voice Messages
- Users can send voice recordings
- The system converts voice to base64 format for AI processing
- Relevant input parameters:
  ```
  msgId: Unique message ID
  msgType: Message type ("voice")
  fromUser: Sender's OpenID
  createTime: Message creation timestamp
  media_id: WeChat media ID for the voice
  voice_base64: Base64 encoded voice data
  voice_media_type: Media type of the voice
  voice_format: Format of the voice (default "amr")
  ```

#### 4. Link Messages
- Users can share links to articles/websites
- The system extracts link information for AI processing
- Relevant input parameters:
  ```
  msgId: Unique message ID
  msgType: Message type ("link")
  fromUser: Sender's OpenID
  createTime: Message creation timestamp
  url: The shared URL
  title: Title of the shared link
  description: Description of the shared link
  ```

Your Dify application can access all these parameters in the conversation context and respond accordingly.

## Technical Architecture

This plugin uses a modular design with the following main components:

### Directory Structure
```
endpoints/
├── wechat/                    # Core WeChat processing module
│   ├── __init__.py            # Package initialization
│   ├── models.py              # WechatMessage model definition
│   ├── parsers.py             # XML parser definition
│   ├── formatters.py          # Response formatter definition
│   ├── factory.py             # Message handler factory
│   ├── crypto.py              # WeChat message encryption tools
│   ├── retry_tracker.py       # Message retry tracker
│   ├── api/                   # API-related
│   │   ├── __init__.py        # API package initialization
│   │   └── custom_message.py  # Customer service message sender
│   └── handlers/              # Message handlers
│       ├── __init__.py        # Handlers package initialization
│       ├── base.py            # Abstract handler base class
│       ├── text.py            # Text message handler
│       ├── image.py           # Image message handler
│       ├── voice.py           # Voice message handler
│       ├── link.py            # Link message handler
│       └── unsupported.py     # Unsupported message type handler
├── wechat_get.py              # Handle WeChat server verification
└── wechat_post.py             # Handle user messages
```

---

## 🌟 Support This Project

If you find this plugin helpful, please consider:

- ⭐ **Star this repository** to show your support
- 🐛 **Report issues** to help improve the plugin
- 💡 **Suggest features** for future development
- 📢 **Share with others** who might benefit from it
- 🤝 **Contribute** by submitting pull requests

**Your support motivates continued development and improvement!**