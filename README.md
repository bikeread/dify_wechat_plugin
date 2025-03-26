# Dify WeChat Official Account Plugin

**Author:** bikeread  
**Version:** 0.0.2
**Type:** extension  

## Overview

The Dify WeChat Official Account Plugin is designed for content creators and public account owners who want to integrate AI capabilities into their WeChat Official Accounts. It provides 24/7 intelligent customer service and content assistance.

## Quick Setup Guide

### Step 1: Configure the Plugin

1. After installing the plugin, create a new endpoint
2. Configure the following settings:
   - **Endpoint Name**: Any name you prefer
   - **APP**: Select the Dify application that will handle user messages
   - **WeChat Token**: Copy from your WeChat Official Account platform
   - **EncodingAESKey**: Copy from your WeChat Official Account platform
   - **AppID**: Your Official Account's AppID
   - **AppSecret**: Your Official Account's AppSecret
   - **Timeout Message**: A message to show when response takes longer than 15 seconds

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

## Plugin Configuration

Required Settings:
- `wechat_token`: Same token as configured in your WeChat Official Account

Encryption Mode Settings:
- `encoding_aes_key`: Same as EncodingAESKey in your WeChat Official Account
- `app_id`: Your Official Account's AppID

Customer Service Message Support:
- `app_secret`: Your Official Account's AppSecret

Optional Settings:
- `timeout_message`: Temporary response message for timeout situations

## Advanced Usage

### Supported Message Types

This plugin supports multiple types of messages that your users can send to your WeChat Official Account:

1. **Text Messages**
   - Users can send regular text messages
   - Relevant input parameters:
     ```
     msgId: Unique message ID
     msgType: Message type ("text")
     fromUser: Sender's OpenID
     createTime: Message creation timestamp
     content: The text message content
     ```

2. **Image Messages**
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

3. **Voice Messages**
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

4. **Link Messages**
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