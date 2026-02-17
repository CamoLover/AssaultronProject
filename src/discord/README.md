# ASR-7 Discord Bot

Discord bot bridge for the ASR-7 AI system. This bot allows you to interact with ASR-7 directly from Discord, with full support for conversation history, memory, and voice messages.

## Features

- **Direct AI Communication**: Talk to ASR-7 by mentioning the bot in any channel or via DM
- **Conversation Memory**: All conversations are stored in the same `conversation_history.json` as the web UI
- **Long-term Memory**: ASR-7 remembers information about users across all platforms
- **Voice Messages**: Enable voice mode to receive audio responses as Discord voice messages
- **Notification Integration**: Discord messages reset the notification counter just like web UI interactions
- **Multi-user Support**: The bot identifies users by their Discord username

## Requirements

- Node.js 18+ (for ES modules support)
- **FFmpeg** (required for voice messages - converts WAV to OGG Opus format)
- Running ASR-7 Flask API server (default: `http://127.0.0.1:8080`)
- Discord bot with proper permissions
- xVAsynth server running (for voice messages)

### Installing FFmpeg

FFmpeg is **required** for voice messages to work. The bot converts WAV files from xVAsynth to OGG Opus format for Discord.

**Windows - Quick install using Chocolatey:**
```bash
choco install ffmpeg -y
```

**Or using Scoop:**
```bash
scoop install ffmpeg
```

**Manual installation:**
1. Download: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your system PATH environment variable
4. **Restart your terminal** for PATH changes to take effect
5. Verify with: `ffmpeg -version`

## Setup

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section
4. Click "Add Bot"
5. Under "Privileged Gateway Intents", enable:
   - Message Content Intent
   - Server Members Intent
6. Copy the bot token

### 2. Get Bot IDs

- **Client ID**: Found under "General Information" > "Application ID"
- **Guild ID** (optional, for faster command registration):
  - Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
  - Right-click your server and select "Copy Server ID"

### 3. Configure Environment Variables

Edit the `.env` file in the parent directory and add:

```env
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_CLIENT_ID=your_discord_client_id_here
DISCORD_GUILD_ID=your_discord_guild_id_here
```

- `DISCORD_BOT_TOKEN`: The bot token from step 1
- `DISCORD_CLIENT_ID`: The application ID from step 2
- `DISCORD_GUILD_ID`: Your server ID (optional, recommended for testing)

### 4. Invite Bot to Server

Use this URL, replacing `YOUR_CLIENT_ID` with your actual Client ID:

```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=274878221376&scope=bot%20applications.commands
```

Permissions included:
- Send Messages
- Send Messages in Threads
- Attach Files
- Read Message History
- Use Slash Commands

### 5. Install FFmpeg (if not already installed)

See the **Installing FFmpeg** section above. The bot will check for FFmpeg on startup and warn if it's not found.

### 6. Install Dependencies

```bash
cd discord
npm install
```

### 7. Start the Bot

```bash
npm start
```

For development with auto-reload:
```bash
npm run dev
```

## Usage

### Talking to ASR-7

**In a Server Channel:**
Mention the bot to get a response:
```
@ASR-7 Hey, how are you doing?
```

**In Direct Messages:**
Just send a message directly (no mention needed)

**User Identification:**
The bot automatically formats messages as:
```
Message from Discord by YourUsername: Your message here
```

This allows ASR-7 to know who is talking and remember conversations with different users.

### Voice Commands

Use the `/voice` slash command to control voice messages:

**Activate Voice:**
```
/voice activate
```
ASR-7 will send audio responses as Discord voice messages in the current channel.

**Deactivate Voice:**
```
/voice deactivate
```
Stop receiving audio responses.

**Check Status:**
```
/voice status
```
View current voice settings and xVAsynth server status.

### LLM Provider Commands

Use the `/llm` slash command to manage the AI provider:

**Change Provider:**
```
/llm change provider:ollama
/llm change provider:gemini
/llm change provider:openrouter
```
Switch the LLM provider. Changes are synced with the web UI.

**Check Status:**
```
/llm status
```
View current LLM provider and model.

### Moderation Commands

**Clear Messages:**
```
/clear number:10
```
Delete a specified number of messages (1-100) from the channel.
*Note: Messages older than 14 days cannot be bulk deleted due to Discord API limitations.*

### Voice Message Flow

1. Enable voice with `/voice activate`
2. Send a message to ASR-7
3. Receive text response immediately
4. Receive audio file shortly after (if voice is enabled)

The bot listens to the AI's voice event stream and automatically sends audio files when they're generated.

## How It Works

### Integration with AI System

The bot communicates with the Flask API server:

- **Chat Endpoint**: `POST /api/chat` - Sends messages and receives responses
- **Notification Endpoints**: Resets notification counters when users interact
- **Voice Endpoints**:
  - `POST /api/voice/start` - Start voice system
  - `GET /api/voice/status` - Check voice status
  - `GET /api/voice/events` - SSE stream for audio events
  - `GET /api/voice/audio/<filename>` - Download audio files

### Notification Counter Reset

Every time a user sends a message, the bot calls:
- `POST /api/notifications/user_active` - Updates last interaction time
- `POST /api/notifications/reset_waiting` - Clears waiting state

This prevents duplicate notifications across platforms.

### Voice Event Stream

When voice is activated, the bot:
1. Opens an EventSource connection to `/api/voice/events`
2. Listens for `audio_ready` events
3. Downloads the audio file from the provided URL
4. Sends it to Discord as an attachment

## Requirements

- Node.js 18+ (for ES modules support)
- Running ASR-7 Flask API server (default: `http://127.0.0.1:5000`)
- Discord bot with proper permissions
- xVAsynth server running (for voice messages)

## Configuration

The bot reads configuration from the parent `.env` file:

```env
# API Connection
API_BASE_URL=http://127.0.0.1:5000  # Optional, defaults to this
API_USERNAME=admin                   # From existing config
API_PASSWORD=your_secure_password_here  # From existing config

# Discord Bot
DISCORD_BOT_TOKEN=your_token
DISCORD_CLIENT_ID=your_client_id
DISCORD_GUILD_ID=your_guild_id  # Optional
```

## Troubleshooting

**Bot doesn't respond:**
- Check that the Flask API server is running
- Verify the bot has "Message Content Intent" enabled
- Check console logs for authentication errors

**Slash commands not appearing:**
- Wait up to 1 hour for global commands to propagate
- Use `DISCORD_GUILD_ID` for instant guild-specific commands
- Try kicking and re-inviting the bot

**Voice messages not working:**
- Ensure xVAsynth server is running
- Check `/voice status` to verify server state
- Look for errors in bot console logs

**"Error executing voice command":**
- Make sure the Flask API server is accessible
- Verify API credentials in `.env`
- Check network connectivity

## Architecture

```
Discord User
    |
    v
Discord Bot (bot.js)
    |
    +--> POST /api/chat (send message)
    |
    +--> POST /api/notifications/* (reset counters)
    |
    +--> SSE /api/voice/events (listen for audio)
    |
    v
Flask API Server (main.py)
    |
    +--> Cognitive Layer (AI processing)
    |
    +--> conversation_history.json (shared storage)
    |
    +--> memories.json (shared memory)
    |
    +--> Voice Manager (xVAsynth)
    |
    v
Response back to Discord
```

## Security Notes

- The bot uses HTTP Basic Auth to communicate with the API
- Keep your `.env` file secure and never commit it to version control
- The bot token should be kept private
- Consider using environment-specific configuration for production

## Future Enhancements

Possible improvements:
- Image upload support from Discord
- Multiple channel support with separate conversation contexts
- Voice channel integration for real-time audio
- Custom emoji reactions based on AI emotion state
- Thread support for organized conversations
