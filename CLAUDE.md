# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Dify WeChat Official Account Plugin that enables integration between Dify AI applications and WeChat Official Accounts, providing 24/7 intelligent customer service and content assistance through WeChat's messaging platform.

## Architecture Overview

### Core Components

1. **Endpoints System**
   - `wechat_get.py`: Handles WeChat server verification (Token validation)
   - `wechat_post.py`: Main message processing with retry mechanism, timeout handling, and customer service message support

2. **Message Processing Pipeline**
   - XML parsing and encryption/decryption (`crypto.py`, `parsers.py`)
   - Handler factory pattern for different message types (`factory.py`)
   - Abstract handler base class with streaming support (`handlers/base.py`)
   - Specific handlers: text, image, voice, link, event, unsupported

3. **Key Features**
   - Retry mechanism with configurable timeout ratio (0.1-1.0)
   - Interactive waiting mode when customer service messages are disabled
   - WeChat API proxy support for bypassing whitelist restrictions
   - Conversation state management with storage persistence
   - Multi-language support (en_US, zh_Hans, ja_JP, pt_BR)

## Common Development Commands

```bash
# Run the plugin server
python main.py

# Install dependencies
pip install -r requirements.txt
```

## Key Configuration Points

### Required Settings
- `app_id`: WeChat Official Account AppID
- `wechat_token`: Token for server verification
- `app`: Dify application selector

### Optional Settings
- `encoding_aes_key`: For encrypted message mode
- `app_secret`: For customer service messages
- `enable_custom_message`: Enable/disable customer service messages
- `wechat_api_proxy_url`: Custom API proxy (default: api.weixin.qq.com)
- `retry_wait_timeout_ratio`: Retry timeout ratio (0.1-1.0, default: 0.7)
- `max_continue_count`: Max interactive waiting retries (default: 2)

## Message Flow

1. **Initial Request**: WeChat sends message → Plugin processes with 5s timeout
2. **Timeout Handling**: 
   - If AI responds within 5s: Direct reply
   - If timeout: Return HTTP 500 → Triggers WeChat retry (up to 3 times)
3. **Retry Strategy**:
   - Retry 1-2: Return HTTP 500 if still processing
   - Retry 3: 
     - With customer service enabled: Send timeout message, then async send full response
     - Without customer service: Interactive waiting mode (user replies "1" to continue)

## Important Implementation Details

### Timeout Constants
- `DEFAULT_HANDLER_TIMEOUT`: 5.0 seconds (fixed, WeChat requirement)
- `RETRY_WAIT_TIMEOUT`: Calculated as 5.0 * retry_wait_timeout_ratio
- `STREAM_CHUNK_TIMEOUT`: 30 seconds for streaming chunks
- `MAX_TOTAL_STREAM_TIME`: 240 seconds total streaming time

### Storage Keys
- Conversation storage: `wechat_conv_{user_id}_{app_id}`
- Clear history command: `/clear`

### Message Status Tracking
- Uses `MessageStatusTracker` for managing retry states
- Tracks completion events, results, and retry counts
- Prevents duplicate message sending

### Thread Safety
- Async message processing with daemon threads
- Thread-safe waiting mechanisms with `threading.Event()`
- Lock-protected user waiting state management

## Error Handling Patterns

1. **Decryption failures**: Return HTTP 400
2. **Verification failures**: Return HTTP 403  
3. **Processing exceptions**: Log error, return empty response (HTTP 200)
4. **Timeout scenarios**: Implement retry mechanism or interactive waiting

## Plugin Manifest Structure

- Version: 0.0.8
- Type: Dify plugin
- Permissions: tool, model (llm, tts, speech2text), endpoint, app, storage
- Memory: 256MB
- Storage: 1GB
- Python version: 3.12