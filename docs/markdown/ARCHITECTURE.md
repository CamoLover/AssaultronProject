# Assaultron Project ASR-7 - System Architecture

## Overview

The Assaultron Project ASR-7 is an **embodied AI agent system** implementing a behavior-based architecture inspired by robotics subsumption architectures and reactive planning systems. The system goes beyond traditional chatbots by implementing a **virtual body** that translates high-level intentions into physical-like states, creating a more immersive and character-driven interaction model.

**Project Type**: Personal AI companion robot with autonomous task execution capabilities
**Architecture Pattern**: Layered Embodied Agent (Cognitive → Behavioral → Motion)
**Primary Language**: Python 3.9+
**AI Models**: Multi-provider support (Ollama local, Google Gemini, OpenRouter/DeepSeek)
**Voice Output**: xVAsynth with Fallout 4 Assaultron voice model (TTS)
**Voice Input**: Mistral Voxtral for real-time speech-to-text transcription (STT)
**Vision**: MediaPipe EfficientDet-Lite0 for real-time object detection

---

## Core Architecture Layers

### 1. Cognitive Layer (`cognitive_layer.py`)

**Purpose**: The "brain" - handles all LLM interaction and high-level reasoning.

**Responsibilities**:
- Process user input through configured LLM provider (Ollama/Gemini/OpenRouter)
- Generate structured `CognitiveState` outputs containing:
  - Goal (what the agent wants to achieve)
  - Emotion (how the agent feels)
  - Confidence & Urgency scores
  - Natural language dialogue
  - Optional memory extraction
- Manage conversation history and long-term memories
- Prevent response duplication through multi-attempt generation
- Format prompts with world context, body state, mood state, vision data, and time awareness

**Key Class**: `CognitiveEngine`

**LLM Provider Support**:
- **Ollama** (local): Default for privacy, runs gemma3:4b
- **Google Gemini**: gemini-2.5-flash with native JSON output and multimodal vision
- **OpenRouter**: Supports DeepSeek-V3.2 and other models

**Mood Integration**:
The cognitive layer receives `MoodState` and formats behavioral guidance for the LLM:
- **High curiosity** → "ask probing questions, show interest in details"
- **High irritation** → "responses are shorter, more terse, slightly sarcastic edge"
- **High boredom** → "responses lack enthusiasm, might be distracted"
- **High attachment** → "more protective, affectionate tone"

This influences the AI's dialogue tone, verbosity, and engagement level while maintaining character consistency.

**Data Flow**:
```
User Message → Enhanced Prompt (system + world + body + mood + vision + time + memory + history) → LLM → JSON Response → CognitiveState
```

**Output Format** (JSON enforced):
```json
{
  "goal": "protect|greet|idle|investigate|...",
  "emotion": "hostile|friendly|curious|neutral|...",
  "confidence": 0.0-1.0,
  "urgency": 0.0-1.0,
  "focus": "entity_id or null",
  "dialogue": "spoken response",
  "memory": "optional long-term memory to store",
  "needs_attention": true/false,
  "attention_reason": "why notification is needed"
}
```

---

### 2. Behavioral Layer (`behavioral_layer.py`)

**Purpose**: Translates cognitive states into body commands using **utility-based behavior selection**.

**Responsibilities**:
- Maintain a library of discrete behaviors (Intimidate, FriendlyGreet, AlertScan, etc.)
- Calculate utility scores for each behavior based on current cognitive state
- Select the highest-utility behavior and execute it
- Generate `BodyCommand` outputs specifying desired body configuration
- Track behavior selection history for debugging

**Key Classes**:
- `Behavior` (abstract base class)
- `BehaviorArbiter` (behavior selector)
- Behavior implementations: `IntimidateBehavior`, `FriendlyGreetBehavior`, `AlertScanBehavior`, `RelaxedIdleBehavior`, `CuriousExploreBehavior`, `ProtectiveBehavior`, `PlayfulBehavior`, `IlluminateBehavior`

**Utility Calculation**:
Each behavior calculates a utility score (0.0-1.0+) based on:
- Goal match (e.g., "intimidate" goal → high utility for IntimidateBehavior)
- Emotion match (e.g., "hostile" emotion → high utility for aggressive behaviors)
- Confidence and urgency scores

**Data Flow**:
```
CognitiveState → Utility Calculation → Behavior Selection → BodyCommand
```

---

### 3. Virtual Body & World Model (`virtual_body.py`)

**Purpose**: Maintains symbolic representation of the agent's body state and world perception.

**Responsibilities**:
- Track virtual body configuration (posture, luminance, hand states)
- Track world state (environment, threat level, detected entities)
- Maintain internal mood state (curiosity, irritation, boredom, attachment)
- Log state transitions for debugging
- Persist mood state across sessions

**Key Data Structures**:

**BodyState**:
- `posture`: idle, alert, aggressive, relaxed, curious
- `luminance`: dim, soft, normal, bright, intense
- `left_hand`, `right_hand`: closed, relaxed, open, pointing
- `head_orientation`: (pitch, yaw, roll) - future expansion

**WorldState**:
- `entities`: List of detected entities from vision system
- `environment`: dark, normal, bright
- `threat_level`: none, low, medium, high
- `time_of_day`: morning/afternoon/evening/night

**MoodState** (emergent internal state):
- `curiosity` (0.0-1.0): Interest in surroundings
- `irritation` (0.0-1.0): Frustration level
- `boredom` (0.0-1.0): Lack of stimulation
- `attachment` (0.0-1.0): Emotional bond to operator
- `engagement`: Derived from curiosity and boredom
- `stress`: Derived from irritation and boredom

**Mood Evolution**:
- Boredom increases with time between interactions
- Curiosity increases with questions
- Irritation increases with very short repetitive messages
- Attachment grows slowly with interaction count
- Natural decay over time to baseline

---

### 4. Motion Controller (`motion_controller.py`)

**Purpose**: The ONLY layer that knows about hardware primitives. Translates symbolic body states into concrete values.

**Responsibilities**:
- Map symbolic states to hardware values (LED intensity 0-100, hand positions 0-100)
- Apply safety constraints and validation
- Maintain backward-compatible hardware state format
- Future: Implement smooth interpolation for transitions

**Hardware Mappings**:
```python
# Luminance → LED Intensity
DIM: 10, SOFT: 35, NORMAL: 50, BRIGHT: 75, INTENSE: 100

# Hand States → Position
CLOSED: 0, RELAXED: 30, OPEN: 70, POINTING: 50

# Posture influences baseline hand positions
IDLE: {left: 0, right: 0}
ALERT: {left: 30, right: 30}
AGGRESSIVE: {left: 0, right: 0}
RELAXED: {left: 50, right: 50}
CURIOUS: {left: 70, right: 70}
```

**Data Flow**:
```
BodyCommand → Hardware Translation → Hardware State Dictionary
```

**Hardware State Format**:
```json
{
  "led_intensity": 0-100,
  "hands": {
    "left": {"position": 0-100, "status": "closed|relaxed|open|pointing"},
    "right": {"position": 0-100, "status": "closed|relaxed|open|pointing"}
  }
}
```

---

## Supporting Systems

### Voice System (`voicemanager.py`)

**Purpose**: TTS (Text-to-Speech) using xVAsynth for character-authentic voice output.

**Components**:
- **Server Management**: Starts/stops xVAsynth server (localhost:8008)
- **Model Loading**: Loads Fallout 4 Assaultron voice model (`f4_robot_assaultron.json`)
- **Async Synthesis**: Queue-based audio generation to prevent blocking
- **Callback Notification**: Fires `on_audio_ready_callback` when synthesis completes; Flask (`main.py`) translates this into Server-Sent Events (SSE) via `/api/voice/events`

**Audio Pipeline**:
```
Dialogue Text → xVAsynth API → WAV File → ai-data/audio_output/ → Frontend Playback
```

**Implementation Notes**:
- Handles port conflicts and server startup retries
- Monitors server logs via threaded stdout/stderr readers
- Provides fallback for startup failures

---

### Speech-to-Text System (`stt_manager.py`)

**Purpose**: Real-time voice input using Mistral's Voxtral API for bidirectional voice communication.

**Components**:
- **MistralSTTManager class**: Manages real-time transcription with async/threading architecture
- **Mistral Voxtral API**: Model `voxtral-mini-transcribe-realtime-2602` for streaming transcription
- **PyAudio Integration**: Captures microphone audio (16kHz, PCM 16-bit mono)
- **Async Transcription**: Streams audio chunks to Mistral API for real-time processing
- **Event Broadcasting**: SSE (Server-Sent Events) for real-time updates to multiple clients

**Key Features**:
- **Real-time Streaming**: Not batch processing - continuous audio streaming with immediate transcription
- **Audio Visualization**: RMS (Root Mean Square) volume calculation at 10Hz for live volume meters
- **Device Selection**: Enumerate and select from available microphone input devices
- **Pause/Resume**: Pause transcription during AI speech to prevent feedback loops
- **Transcript Buffer**: Accumulates partial transcriptions into full text
- **Configurable Audio**: Adjustable sample rate and chunk duration via environment variables

**Audio Pipeline**:
```
Microphone → PyAudio (16kHz PCM) → 480ms chunks → Mistral Voxtral API → Transcription deltas → Full transcript
```

**Event Types**:
- `transcription_started` - Session created, ready to transcribe
- `transcription_partial` - Real-time text delta + accumulated full text
- `transcription_complete` - Final transcript for completed phrase
- `transcription_error` - API errors or processing failures
- `audio_level` - Volume meter updates (0-100%) at 10Hz
- `transcription_paused` / `transcription_resumed` - Pause state changes
- `transcription_stopped` - Session ended

**Implementation Notes**:
- Uses async/await pattern with threading for non-blocking operation
- Calculates RMS (Root Mean Square) for normalized volume levels (0-100%)
- Thread-safe event broadcasting to multiple SSE client queues
- Graceful device switching (stops current stream, changes device, restarts)
- Optional system - gracefully degrades if `mistralai` or `pyaudio` packages unavailable

**Integration with Voice System**:
- Voice Output (TTS): xVAsynth generates speech responses
- Voice Input (STT): Mistral Voxtral captures user speech
- Together they enable full bidirectional voice conversation
- STT pauses during TTS playback to avoid transcribing AI's own voice

---

### Vision System (`vision_system.py`)

**Purpose**: Webcam-based perception layer using MediaPipe for object detection.

**Components**:
- **Object Detection**: MediaPipe EfficientDet-Lite0 (CPU-optimized, fast)
- **Camera Management**: Enumerate, select, start/stop capture
- **Real-time Processing**: Background thread captures frames at 30 FPS; object detection runs at ~10 FPS
- **Entity Tracking**: Converts detections to `DetectedEntity` objects
- **Scene Analysis**: Generates scene descriptions and threat assessments

**Detected Information**:
- Person count
- Object classes (cup, laptop, chair, etc.)
- Bounding boxes and confidence scores
- Threat assessment (alerts for weapons)
- Raw frame (for multimodal LLM vision)
- Annotated frame (for UI display)

**Integration with Embodied Architecture**:
- Vision entities fed into `WorldState.entities`
- Threat level updates `WorldState.threat_level`
- Scene descriptions included in cognitive layer prompt
- Raw frames sent to multimodal LLMs (Gemini) for detailed visual reasoning

**Detection Classes** (80+ from COCO dataset):
- People, animals (cat, dog, bird)
- Common objects (cup, bottle, laptop, phone)
- Furniture (chair, couch, bed)
- Alert classes (knife, scissors - triggers threat warnings)

---

### Autonomous Agent System

#### Agent Logic (`agent_logic.py`)

**Purpose**: Implements autonomous task execution using ReAct (Reasoning + Acting) pattern.

**Components**:
- **Task Decomposition**: Breaks complex tasks into steps
- **Iterative Reasoning Loop**:
  1. **Thought**: Analyze situation and decide next action
  2. **Action**: Execute tool with parameters
  3. **Observation**: Process results and update state
  4. **Repeat** until task complete (max 30 iterations)
- **Tool Registry**: File operations, web search, email, git
- **Self-Correction**: Recovers from errors and retries
- **Project Memory**: Persists task history in `.agent_history.json`

**Available Tools**:
- **File Operations**: create_file, edit_file, read_file, delete_file, create_folder, list_files
- **System**: run_command (sandboxed)
- **Web**: web_search (Brave API)
- **Email**: send_email, read_emails, reply_to_email, forward_email, get_email_status (if configured)
- **Git**: git_clone, git_commit, git_push, git_pull, list_git_repositories, git_status, get_git_config (if configured)

**Agent Prompt Structure**:
```
ASR-7 Personality + Autonomous Task Mode Instructions + Tool Descriptions + Reasoning History
```

**Example Agent Flow**:
```
User: "Create a website about Lego"

Thought: I need to create an HTML file with Lego content
Action: create_file(name="lego_website.html", content="<html>...")
Observation: File created successfully at sandbox/lego_website.html

Thought: Task complete, website created
Action: Final Answer: "Website created! Check out lego_website.html"
```

#### Sandbox Manager (`sandbox_manager.py`)

**Purpose**: Secure execution environment for agent file operations.

**Security**:
- All operations restricted to `SANDBOX_PATH` directory (default: `./src/sandbox`)
- Path validation prevents directory traversal attacks
- Command execution sandboxed within workspace

**Operations**:
- File CRUD (create, read, update, delete)
- Folder management
- Command execution (git, npm, python, etc.)
- File existence checks

---

### Discord Bot Integration (`src/discord/bot.js`)

**Purpose**: Multi-channel user interaction via Discord platform.

**Technology**: Node.js with discord.js library

**Key Features**:
- **Message Handling**:
  - Responds to bot mentions in Discord servers
  - Supports Direct Messages (DMs)
  - Tracks active channel for multi-location conversations
  - Auto-splits responses exceeding 2000-character Discord limit
  - Resets notification counter on user interaction

- **Slash Commands**:
  - `/voice activate|deactivate|status` - Control xVAsynth voice system
  - `/llm change [provider]|status` - Switch between ollama/gemini/openrouter
  - `/clear [number]` - Delete a specified number of messages (1-100) from the channel
  - Uses Discord embeds for formatted responses

**Voice Message Integration**:

The Discord bot can send AI responses as native Discord voice messages when voice is enabled:

**Voice Message Pipeline**:
```
AI Dialogue → xVAsynth (WAV) → Discord Bot Downloads → FFmpeg Conversion (WAV→OGG Opus) → Discord CDN Upload → Voice Message Posted
```

**Technical Flow**:
1. Bot listens to `/api/voice/events` SSE stream
2. Receives `audio_ready` event with WAV file URL
3. Downloads WAV file from AI server via authenticated request
4. Converts WAV to OGG Opus using FFmpeg (48kHz, 64k bitrate)
5. Extracts audio metadata (duration via ffprobe, waveform data)
6. Requests upload URL from Discord API
7. Uploads OGG file to Discord CDN
8. Posts message with `IS_VOICE_MESSAGE` flag and metadata
9. Cleans up temporary files

**FFmpeg Integration**:
- Checks for FFmpeg availability on startup
- Provides user-friendly error messages if missing
- Uses `ffmpeg` for conversion and `ffprobe` for metadata extraction

**Server-Sent Events (SSE) Connection**:
- Maintains persistent connection to `/api/voice/events`
- Listens for three event types:
  - `audio_ready` - Triggers voice message sending
  - `agent_completion` - Broadcasts agent task results to channel
  - `voice_notification` - Handles voice system status changes
- Auto-reconnects if connection drops while voice is enabled
- Only active when voice system is running

**Integration with Main System**:
- Authenticates with AI server using HTTP Basic Auth (API_USERNAME, API_PASSWORD)
- Sends messages to `/api/chat` endpoint with `source: "discord"` tag
- Posts bot status to `/api/monitoring/discord_status` for dashboard tracking
- Resets notification system on user activity

**Configuration** (.env):
```bash
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_CLIENT_ID=your_client_id
DISCORD_GUILD_ID=optional_guild_id
API_BASE_URL=http://127.0.0.1:8080
API_USERNAME=your_api_username
API_PASSWORD=your_api_password
```

**Implementation Notes**:
- Node.js subprocess managed by `run.py`
- Handles Discord API rate limits gracefully
- Tracks pending voice responses to prevent duplicates
- Logs all operations for debugging

---

### Notification System (`notification_manager.py`)

**Purpose**: Proactive attention requests via Discord webhooks.

**Features**:
- **Inactivity Monitoring**: Sends check-ins after 5-30 minutes of no interaction
- **Threat Alerts**: Notifies on vision system threat detection
- **Rate Limiting**: Prevents notification spam
- **AI-Generated Messages**: Uses cognitive engine to create natural check-in messages
- **Timeout Handling**: Waits for user response before sending next notification

**Configuration**:
- `min_interval`: Minimum time between notifications (30s default)
- `inactivity_threshold_min`: Minimum time before check-in (5min)
- `inactivity_threshold_max`: Maximum time before check-in (30min)

**Integration Points**:
- `_check_and_send_notifications()` called after each user message
- Background monitoring thread checks for threats when user is idle
- Vision system provides threat data

---

### Time Awareness System (`time_awareness.py`)

**Purpose**: Provides temporal context to enhance AI personality.

**Data Provided**:
- Current date, time, day of week
- Time since last message
- Interaction patterns (late nights, long gaps)
- Session duration
- Mood correlation with time patterns

**Prompt Integration**:
```
TIME AWARENESS:
Current time: 2026-02-10 23:45 (Monday night)
Time since last message: 3 hours
Pattern: Late night session (11:45 PM)
Mood: attachment=0.7, boredom=0.3
```

**Personality Impact**:
- AI comments on late nights: "Up late again, boss?"
- Notices long gaps: "Three hours? Did you forget about me?"
- Adjusts concern level based on time patterns

---

### Email & Git Management

#### Email Manager (`email_manager.py`)

**Purpose**: Complete email management system for AI agent communications.

**Features**:
- **Send emails** via SMTP with CC/BCC support
- **Read emails** from IMAP folders
- **Reply to emails** with quoted original messages
- **Forward emails** with custom messages
- **Automatic email signature** (configurable)
- **Rate limiting** (default: 10/hour, configurable in .env)
- **Domain whitelist** for security
- **HTML and plain text** support
- **Discord logging** for all email activities

**Email Operations**:

1. **send_email(to, subject, body, body_html, cc, bcc, add_signature)**
   - Supports multiple recipients (comma-separated or list)
   - Optional CC and BCC recipients
   - Automatic signature appended (can be disabled)
   - Domain validation for all recipients
   - Rate limit checking before send

2. **reply_to_email(email_id, reply_body, reply_body_html, cc, folder)**
   - Fetches original email from IMAP
   - Automatically adds "Re:" prefix to subject
   - Quotes original message in reply
   - Preserves conversation context

3. **forward_email(email_id, to, forward_message, cc, folder)**
   - Forwards complete email with headers
   - Adds "Fwd:" prefix to subject
   - Optional custom message before forwarded content
   - Includes original From/Date/Subject/To headers

4. **read_emails(folder, limit, unread_only)**
   - Reads from specified IMAP folder (default: INBOX)
   - Filters for unread messages (configurable)
   - Returns structured email objects with id, from, to, subject, date, body

**Email Signature**:
- Automatically generated in plain text and HTML formats
- Includes AI name, role, email address, and branding
- Configurable via `EMAIL_SIGNATURE_ENABLED` and `AI_NAME` environment variables
- Example format:
  ```
  ---
  Assaultron AI
  Autonomous AI Assistant
  Email: asr-7@camolover.dev
  Powered by Camolover
  ```

**Security Features**:
- Domain whitelist validation (all recipients checked)
- Rate limiting with timestamp tracking (thread-safe)
- Enabled/disabled via `EMAIL_ENABLED` flag
- Discord webhook logging for monitoring
- SMTP with TLS encryption (STARTTLS)
- IMAP with SSL encryption

**Configuration** (.env):
```bash
AI_EMAIL_ADDRESS=asr-7@camolover.dev
AI_EMAIL_PASSWORD=your_password
SMTP_SERVER=smtp.server.com
SMTP_PORT=587
IMAP_SERVER=imap.server.com
IMAP_PORT=993
EMAIL_ENABLED=true
EMAIL_RATE_LIMIT=10
ALLOWED_EMAIL_DOMAINS=gmail.com,yahoo.com,example.com
EMAIL_SIGNATURE_ENABLED=true
AI_NAME=Assaultron AI
DISCORD_LOG_URL=your_webhook_url
```

**Agent Tool Integration** (`agent_tools.py`):
- `send_email()` - Send new emails with full CC/BCC support
- `read_emails()` - Check inbox for messages
- `reply_to_email()` - Intelligently reply to existing emails
- `forward_email()` - Forward emails to other recipients
- `get_email_status()` - Check email system configuration

#### Git Manager (`git_manager.py`)

**Purpose**: Multi-repository Git management in sandbox.

**Features**:
- Clone repositories (HTTPS or SSH)
- Commit changes with AI-generated messages
- Push/pull from remotes
- Repository status tracking
- SSH key support

**Configuration** (.env):
```
GITHUB_USERNAME=
GITHUB_TOKEN=
SSH_KEY_PATH=./ssh/ai_github_key
GIT_USER_NAME=AI Bot
GIT_USER_EMAIL=
GIT_ENABLED=false
```

#### Autonomous Agent Configuration

**Sandbox Path** (.env):
```
SANDBOX_PATH=./src/sandbox
```

All autonomous agent file operations are restricted to this directory for security.

---

### Monitoring & Observability System

**Purpose**: Production-grade system performance monitoring and metrics collection.

#### Monitoring Service (`monitoring_service.py`)

**Core Component**: `MetricsCollector` class - Thread-safe metrics tracking

**Metrics Tracked**:

**1. API Response Times**:
- Endpoint path
- Duration in milliseconds
- HTTP status code
- Timestamp
- Calculates min/avg/max statistics

**2. Voice Processing Times**:
- Text length
- Synthesis duration (ms)
- Success/failure status
- Tracks successful generations for performance analysis

**3. LLM Requests**:
- Model name (Ollama/Gemini/OpenRouter)
- Prompt tokens
- Response tokens
- Total tokens consumed
- Inference duration (ms)
- Cumulative token usage tracking

**4. System Delays**:
- Component name (e.g., "cognitive_engine", "behavior_arbiter")
- Duration in milliseconds
- Optional details field
- Identifies bottlenecks between system components

**5. Message Pipeline**:
- Full message processing stages
- Timing for each pipeline step
- End-to-end latency tracking

**6. Error Logging**:
- Timestamp
- Component that errored
- Error message
- Exception details
- Last 1000 errors stored

**Performance Counters**:
- `total_messages` - Messages processed through pipeline
- `total_api_calls` - All API endpoint calls
- `total_voice_generated` - Successful voice syntheses
- `total_llm_tokens` - Cumulative token usage across all models
- `total_errors` - All errors encountered

**System Status Flags**:
- `ai_active` - AI core running status
- `voice_enabled` - Voice system active status
- `discord_bot_active` - Discord bot connection status
- `current_requests` - Concurrent request counter

**Data Structure**:
- Thread-safe operations using `threading.Lock()`
- Configurable history size (default: 1000 items)
- Uses `collections.deque` with `maxlen` for automatic rotation
- In-memory storage (no database required)

#### Monitoring Dashboard (`monitoring_dashboard.py`)

**Purpose**: Live web interface for real-time metrics visualization.

**Port**: 8081 (separate Flask instance from main AI on 8080)

**Dashboard Features**:

**1. Live Status Panel**:
- System uptime (formatted as hours:minutes:seconds)
- AI Core status indicator (Online/Offline with color-coded badges)
- Voice Synthesis status indicator
- Discord Bot status indicator
- Total messages processed counter

**2. Real-time Metrics Charts** (Chart.js visualizations):
- **API Performance Panel**: Average/min/max response times with 20-point line chart
- **Voice Processing Panel**: Voice synthesis performance with line chart
- **LLM Performance Panel**: Inference time and average tokens per request
- Auto-updates every second via SSE stream

**3. Recent Errors Panel**:
- Scrollable log of last 50 errors
- Timestamp, component, and error message
- Auto-scrolls to latest error

**4. Dark Mode Toggle**:
- Persistent preference via localStorage
- Synchronized color scheme across all charts
- Smooth transitions between themes

**Export Capabilities**:
- **JSON Export**: Download all metrics via `/api/export` endpoint
- **Markdown Reports**: Auto-generated on system shutdown
  - Saved to `debug/reports/monitoring_report_YYYYMMDD_HHMMSS.md`
  - Contains full metrics summary, performance stats, error logs
  - Triggered by `atexit` hook in `run.py`

**API Endpoints** (Dashboard on port 8081):
- `GET /` - Dashboard HTML interface
- `GET /api/stats` - Current statistics summary (JSON)
- `GET /api/metrics/<metric_name>` - Time series data for specific metric
- `GET /api/stream` - Server-Sent Events stream (1-second interval updates)
- `GET /api/export` - Export all metrics as JSON

**Integration with Main System**:
- Main AI server (`main.py`) imports `get_monitoring_service()` singleton
- Records metrics at key points in message processing pipeline
- Discord bot posts status via `POST /api/monitoring/discord_status`
- No performance impact on main system (async metrics collection)

**Startup**:
- Launched first by `run.py` to track all other services
- Runs in daemon thread
- Graceful shutdown with report generation

---

### Multi-Service Architecture (`run.py`)

**Purpose**: Unified launcher for all Assaultron system services.

**Toggleable Services** (boolean configuration flags):
```python
START_ASR = True            # ASR-7 AI Interface (main.py) on port 8080
START_DOCS = True           # Documentation website on port 8000
START_DISCORD_BOT = True    # Discord bot (Node.js)
START_MONITORING = True     # Monitoring dashboard on port 8081
```

**Service Startup Order** (optimized for dependencies):
1. **Monitoring Dashboard** (port 8081) - Starts first to track all other services
2. **Discord Bot** (Node.js subprocess) - Connects to AI server and Discord
3. **ASR-7 AI Interface** (port 8080) - Main Flask application (daemon or main thread)
4. **Documentation Website** (port 8000) - HTTP server (blocking call, keeps main thread alive)

**Threading Model**:
- **Monitoring**: Daemon thread running `monitoring_dashboard.start_monitoring_dashboard()`
- **Discord Bot**: Daemon thread running `subprocess.run(['node', 'bot.js'])`
- **ASR-7**: Daemon thread running `app.run()` (if docs enabled) OR main thread (if docs disabled)
- **Docs**: Blocking call to `httpd.serve_forever()` in main thread

**Shutdown Management**:
- **Graceful Shutdown**: Ctrl+C signal handler catches `KeyboardInterrupt`
- **Monitoring Report Generation**: `atexit` hook calls `generate_shutdown_report()`
  - Creates timestamped markdown report in `debug/reports/` directory
  - Contains final metrics snapshot, performance summary, error logs
- **Service Cleanup**: All daemon threads terminate when main thread exits

**Service Ports Summary**:
| Service | Port | Technology |
|---------|------|------------|
| ASR-7 AI Interface | 8080 | Flask (Python) |
| Documentation Website | 8000 | HTTP Server (Python) |
| Monitoring Dashboard | 8081 | Flask (Python) |
| Discord Bot | - | discord.js (Node.js) |

**Requirements Check**:
- Verifies Flask and requests packages installed
- Auto-installs from `requirements.txt` if missing
- Node.js and npm required for Discord bot

**Process Management**:
- Each service runs independently
- Failures in one service don't crash others (except main AI crashes docs)
- Logs startup status for each service
- Clear console output showing access URLs

---

## Main Application (`main.py`)

### EmbodiedAssaultronCore Class

**Purpose**: Orchestrates all systems and implements the main message processing pipeline.

**Initialization Sequence**:
1. Setup logging with rotation
2. Initialize virtual world (body + environment + mood)
3. Initialize cognitive engine (LLM interface)
4. Initialize behavior arbiter (behavior selector)
5. Initialize motion controller (hardware translation)
6. Initialize voice system
7. Initialize vision system
8. Initialize notification manager
9. Initialize autonomous agent (sandbox + agent logic)

**Message Processing Pipeline**:

```python
def process_message(user_message, image_path=None) -> dict:
    # 1. Analyze message for world cues (threat detection keywords)
    world_updates = analyze_user_message_for_world_cues(message)
    virtual_world.update_world(**world_updates)

    # 2. Update mood based on interaction patterns
    virtual_world.update_mood(user_message, is_question, length)

    # 3. Detect autonomous task requests
    task_detected, task_description = _detect_agent_task(message)
    if task_detected:
        # Start agent in background, return acknowledgment
        return acknowledgment_response

    # 4. Integrate vision data
    if vision_enabled:
        vision_entities = vision_system.get_entities()
        virtual_world.update_world(entities=vision_entities)
        vision_image_b64 = vision_system.get_raw_frame_b64()

    # 5. Cognitive Layer - LLM generates intent
    cognitive_state = cognitive_engine.process_input(
        user_message, world_state, body_state, mood_state,
        memory_summary, vision_context, vision_image_b64, image_path
    )

    # 6. Behavioral Layer - Select behavior
    body_command = behavior_arbiter.select_and_execute(
        cognitive_state, body_state
    )

    # 7. Motion Controller - Translate to hardware
    hardware_state = motion_controller.apply_body_command(body_command)

    # 8. Update virtual body
    virtual_world.update_body(body_command)

    # 9. Memory extraction (AI decides what to remember)
    if cognitive_state.memory:
        cognitive_engine.manage_memory(cognitive_state.memory)

    # 10. Check for notification triggers
    _check_and_send_notifications(cognitive_state, world_state)

    # 11. Voice synthesis (if enabled)
    if voice_enabled:
        voice_system.synthesize_async(cognitive_state.dialogue)

    # 12. Return complete response
    return {
        "dialogue": cognitive_state.dialogue,
        "cognitive_state": {...},
        "body_command": {...},
        "hardware_state": {...},
        "mood": {...}
    }
```

**Task Detection** (for autonomous agent):
- **Agent Override Check**: Before any detection logic runs, the system checks for explicit opt-out phrases in the user's message. If phrases like "don't use agent", "don't call agent", "no agent", "skip agent", "without agent", etc. are detected, the task detection immediately returns `False` — bypassing both LLM classification and keyword fallback. This allows users to include task-like language without triggering the autonomous agent.
- Uses LLM to classify if message is an actionable task
- Fallback to keyword matching if LLM fails, using a two-part system:
  - **Action verbs** (20+): create, make, build, write, generate, develop, code, program, design, implement, construct, research, find, search, look up, investigate, analyze, test, run, execute, deploy
  - **Creation indicators** (14+): website, web page, html, css, javascript, php, file, folder, directory, script, program, app, application, project, code, document, poem, story, article, report, summary
  - Task detected when **both** an action verb AND a creation indicator are present
- Returns enhanced task description with personality

---

## Flask REST API Endpoints

### Core Endpoints

**Chat & Status**:
- `POST /api/chat` - Main chat endpoint (rate limited: 100/min)
- `POST /api/chat/upload_image` - Upload image attachments
- `GET /api/status` - System status and metrics
- `GET /api/logs` - Recent system logs
- `GET /api/history` - Conversation history
- `POST /api/history/clear` - Clear conversation history

**Memory & Debug**:
- `GET /api/memory` - Get memory context (last 20 entries)
- `GET /api/debug/last_response` - Debug: last raw LLM response
- `GET /api/tools/available` - List available agent tools
- `GET /chat_images/<filename>` - Serve uploaded chat image attachments

**Health & Monitoring**:
- `GET /health` - Health check with system metrics
- `GET /api/metrics` - Prometheus-compatible metrics

### Embodied Agent Endpoints

- `GET /api/embodied/virtual_world` - Complete virtual world state
- `GET /api/embodied/body_state` - Current body state
- `GET /api/embodied/world_state` - Current world perception
- `GET /api/embodied/mood_state` - Internal mood state (read-only)
- `POST /api/embodied/mood_state` - Manually adjust mood (UI control)
- `GET /api/embodied/mood_history` - Mood changes over time
- `GET /api/embodied/behavior_history` - Behavior selection history
- `GET /api/embodied/behaviors` - Available behaviors list
- `GET /api/embodied/state_history` - Body state transitions

### Long-Term Memory Endpoints

- `GET /api/embodied/long_term_memories` - Get core memories
- `POST /api/embodied/long_term_memories/add` - Manually add memory
- `POST /api/embodied/long_term_memories/edit` - Edit existing memory
- `POST /api/embodied/long_term_memories/delete` - Remove memory

### Hardware Control (Manual Override)

- `GET /api/hardware` - Current hardware state
- `POST /api/hardware/led` - Set LED intensity (0-100)
- `POST /api/hardware/hands` - Set hand positions (0-100)

### Voice System Endpoints

- `POST /api/voice/start` - Start xVAsynth server and load model
- `POST /api/voice/stop` - Stop voice system
- `POST /api/voice/speak` - Manual speech synthesis
- `GET /api/voice/status` - Voice system status (exempt from rate limit)
- `GET /api/voice/audio/<filename>` - Serve generated audio files
- `GET /api/voice/events` - SSE stream for real-time audio notifications
  - **Purpose**: Broadcasts voice-related events to connected clients (web UI, Discord bot)
  - **Event Types**:
    - `audio_ready` - Emitted when WAV file is generated (includes filename and URL)
    - `agent_completion` - Sent when autonomous agent completes task
    - `voice_notification` - Voice system status changes
  - **Keepalive**: 30-second timeout to maintain connection
  - **Used by**: Frontend for audio playback notifications, Discord bot for voice message triggering
  - **Authentication**: Public endpoint (no auth required)

### Speech-to-Text Endpoints

- `POST /api/stt/start` - Start microphone capture and real-time transcription
- `POST /api/stt/stop` - Stop capturing audio and end transcription session
- `POST /api/stt/pause` - Pause transcription (e.g., while AI is speaking to avoid feedback)
- `POST /api/stt/resume` - Resume transcription after pause
- `GET /api/stt/status` - Get STT system status (listening, paused, model info)
- `GET /api/stt/events` - SSE stream for transcription events
  - **Purpose**: Broadcasts real-time transcription updates to connected clients
  - **Event Types**:
    - `transcription_started` - Session created, ready to transcribe
    - `transcription_partial` - Real-time text delta with accumulated full text
    - `transcription_complete` - Final transcript for completed phrase
    - `transcription_error` - API errors or processing failures
    - `audio_level` - Volume meter updates (0-100%) at 10Hz
    - `transcription_paused` / `transcription_resumed` - Pause state changes
    - `transcription_stopped` - Session ended
  - **Keepalive**: 30-second timeout to maintain connection
  - **Used by**: Frontend for live transcription display and volume visualization
  - **Authentication**: Public endpoint (no auth required)
- `GET /api/stt/devices` - List available microphone input devices
- `POST /api/stt/set_device` - Change active microphone device (restarts stream if listening)
- `POST /api/stt/clear` - Clear transcript buffer manually

### Vision System Endpoints

- `GET /api/vision/status` - Vision system status
- `GET /api/vision/cameras` - List available cameras
- `POST /api/vision/select_camera` - Select camera by ID
- `POST /api/vision/start` - Start vision capture
- `POST /api/vision/stop` - Stop vision capture
- `POST /api/vision/toggle` - Toggle vision on/off
- `GET /api/vision/frame` - Current frame as base64 JPEG
- `GET /api/vision/entities` - Currently detected entities
- `GET /api/vision/scene` - Scene description for AI
- `POST /api/vision/confidence` - Set detection confidence threshold

### Notification System Endpoints

- `POST /api/notifications/test` - Send test notification
- `POST /api/notifications/request_attention` - Manual attention request
- `GET /api/notifications/config` - Get notification settings
- `POST /api/notifications/config` - Update notification settings
- `POST /api/notifications/inactivity/toggle` - Start/stop inactivity monitoring
- `POST /api/notifications/background/toggle` - Start/stop threat monitoring
- `POST /api/notifications/reset_waiting` - Reset waiting flag (debug)
- `POST /api/notifications/user_active` - Mark user active (heartbeat, exempt from rate limit)

### Autonomous Agent Endpoints

- `POST /api/agent/task` - Submit task to agent (rate limited: 10/min)
- `GET /api/agent/status/<task_id>` - Get task status
- `GET /api/agent/tasks` - List all agent tasks
- `POST /api/agent/stop/<task_id>` - Stop running task

### Email Endpoints (auth required)

- `POST /api/email/send` - Send email (supports cc, bcc, add_signature params)
- `POST /api/email/reply` - Reply to existing email
- `POST /api/email/forward` - Forward email to another recipient
- `GET /api/email/read` - Read emails from inbox
- `GET /api/email/status` - Email manager status and configuration

### Git Endpoints (auth required)

- `GET /api/git/repositories` - List git repos in sandbox
- `GET /api/git/status` - Get repo status
- `POST /api/git/commit` - Create commit
- `POST /api/git/push` - Push to remote
- `POST /api/git/pull` - Pull from remote
- `POST /api/git/clone` - Clone repository
- `GET /api/git/config` - Git manager configuration

### Settings

- `GET /api/settings/provider` - Get current LLM provider
- `POST /api/settings/provider` - Switch LLM provider (ollama/gemini/openrouter)

### Monitoring Endpoints (auth required)

- `POST /api/monitoring/discord_status` - Update Discord bot status
  - **Body**: `{"active": true/false}`
  - **Purpose**: Discord bot reports connection status to monitoring dashboard
  - **Updates**: `discord_bot_active` flag in system status

**Note**: Monitoring dashboard runs on separate port 8081 with its own API:
- `GET /` (port 8081) - Monitoring dashboard UI
- `GET /api/stats` (port 8081) - Current statistics summary
- `GET /api/metrics/<metric_name>` (port 8081) - Time series data
- `GET /api/stream` (port 8081) - SSE stream for real-time updates
- `GET /api/export` (port 8081) - Export all metrics as JSON

---

## Configuration (`.env` and `config.py`)

All configuration is now stored in `.env` for easier deployment and security.

### LLM Configuration (.env)

```bash
LLM_PROVIDER=gemini  # "ollama" | "gemini" | "openrouter"

# Gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash

# OpenRouter
OPENROUTER_KEY=your_key_here
OPENROUTER_MODEL=deepseek/deepseek-v3.2

# Ollama (local)
OLLAMA_URL=http://localhost:11434
AI_MODEL=gemma3:4b
```

### Voice Configuration (.env)

```bash
XVASYNTH_PATH=./Content/xVAsynth
VOICE_MODEL=f4_robot_assaultron
```

### Speech-to-Text Configuration (.env)

```bash
# Mistral Voxtral API
MISTRAL_KEY=your_mistral_api_key_here

# Audio capture settings
STT_SAMPLE_RATE=16000           # Audio sample rate in Hz (recommended: 16000)
STT_CHUNK_DURATION_MS=480       # Audio chunk duration in milliseconds
```

**STT Notes**:
- `MISTRAL_KEY` required for STT functionality - system gracefully disables STT if not provided
- Sample rate 16000Hz recommended by Mistral Voxtral for optimal accuracy
- Chunk duration 480ms balances transcription latency and accuracy
- System checks for `mistralai[realtime]` and `pyaudio` packages - logs warnings if unavailable

### Discord Bot Configuration (.env)

```bash
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_CLIENT_ID=your_client_id
DISCORD_GUILD_ID=optional_guild_id  # For guild-specific slash commands
API_BASE_URL=http://127.0.0.1:8080  # AI server URL
API_USERNAME=your_api_username       # For authenticating to AI server
API_PASSWORD=your_api_password       # For authenticating to AI server
```

`config.py` loads these values using `os.getenv()` with sensible defaults.

### Personality Prompt

Contains `ASSAULTRON_PROMPT` - the core system prompt defining ASR-7's personality:
- 25% Friendly, 70% Sarcastic, 5% Flirtatious
- Embodied agent instructions (express goals/emotions, not hardware)
- Vision integration rules
- Time awareness guidelines
- Memory formation guidelines

---

## Data Persistence

### Files Created

**Runtime State**:
- `ai-data/conversation_history.json` - Conversation exchanges (max 100, last 8 sent to LLM)
- `ai-data/memories.json` - Long-term core memories (max 10 via AI-managed path, max 50 via manual add; last 15 sent to LLM, LLM-managed)
- `ai-data/mood_state.json` - Current mood state (persists across sessions)

**Agent Workspace**:
- `src/sandbox/.agent_history.json` - Agent task history (last 50 tasks)
- `src/sandbox/<user_projects>/` - Agent-created files and folders

**Audio Output**:
- `ai-data/audio_output/*.wav` - Generated voice audio files

**Logs**:
- `debug/logs/assaultron.log` - Main log file (rotating, 10MB max, 5 backups)
- `debug/logs/assaultron_errors.log` - Errors only (rotating, 10MB max, 3 backups)

**Chat Images**:
- `ai-data/chat_images/*.jpg|png|gif|webp` - User-uploaded image attachments

**Monitoring Reports**:
- `debug/reports/monitoring_report_*.md` - Generated on system shutdown with timestamp
  - Full metrics summary (API, voice, LLM performance)
  - Performance statistics (min/avg/max for all tracked metrics)
  - Error logs
  - System status snapshot

---

## Security Features

### Authentication

- **HTTP Basic Auth**: API endpoints for email/git (username/password)
- Credentials stored in `.env`: `API_USERNAME`, `API_PASSWORD`

### Rate Limiting

- General endpoints: 200/day, 50/hour
- Chat endpoint: 100/minute
- Agent tasks: 10/minute
- Voice events & user_active: Exempt (heartbeat endpoints)

### Sandbox Security

- All agent file operations restricted to `SANDBOX_PATH` (default: `./src/sandbox`)
- Path validation prevents directory traversal
- Command execution sandboxed within workspace

### Email Security

- Rate limiting: Configurable (default 10/hour)
- Domain whitelist: `ALLOWED_EMAIL_DOMAINS`
- Only sends if `EMAIL_ENABLED=true`

### Discord Bot Security

- **Token-based Authentication**: Securely connects to Discord using `DISCORD_BOT_TOKEN`
- **HTTP Basic Auth**: Authenticates to AI server using username/password
- **No System Access**: Bot has no command execution privileges on host system
- **Sandboxed Audio Conversion**: Temporary WAV/OGG files cleaned up after processing
- **Rate Limit Compliance**: Respects Discord API rate limits
- **No Privilege Escalation**: Limited to Discord API and AI server communication only

---

## Dependencies

### Core

```
flask>=2.0.0
psutil>=5.8.0
requests>=2.25.0
python-dotenv>=1.0.0
```

### Security & Monitoring

```
flask-httpauth>=4.8.0
flask-limiter>=3.5.0
```

### Vision

```
opencv-python>=4.8.0
mediapipe>=0.10.9
numpy>=1.24.0
```

### Voice

- xVAsynth (bundled in `Content/xVAsynth/`)

### Speech-to-Text

```
mistralai[realtime]>=1.0.0  # Mistral Voxtral API with real-time streaming
pyaudio>=0.2.14             # Microphone audio capture
```

**System Dependencies**:
- **PyAudio**: Requires system audio libraries (PortAudio)
  - Windows: Included with pip install
  - Linux: `sudo apt-get install portaudio19-dev python3-pyaudio`
  - macOS: `brew install portaudio`

### AI

```
google-generativeai>=0.3.0  # For Gemini support
```

### Discord Bot (Node.js)

```json
{
  "dependencies": {
    "discord.js": "^14.x",
    "dotenv": "^16.x",
    "axios": "^1.x",
    "eventsource": "^2.x"
  }
}
```

**System Dependencies**:
- **FFmpeg** - Required for WAV to OGG Opus conversion for Discord voice messages
  - Used by Discord bot for audio format conversion

### Optional

- Ollama (local LLM server)
- Brave Search API key (for web search)
- Discord webhook URLs (for notifications)
- Discord bot token (for Discord integration)

---

## Execution Flow Example

### User Message: "It's too dark in here"

1. **World Analysis**: Detects "dark" keyword → sets `environment = "dark"`
2. **Mood Update**: Interaction resets boredom, updates engagement
3. **Vision Check**: If enabled, provides visual context (empty room, no threats)
4. **Cognitive Processing**:
   - LLM receives: personality, world state (dark environment), body state, mood, vision data
   - Outputs: `{"goal": "provide_illumination", "emotion": "helpful", "confidence": 0.9, "urgency": 0.5, "dialogue": "Too dark for you, sweetheart? Let me light things up."}`
5. **Behavior Selection**:
   - IlluminateBehavior scores highest utility (0.9)
   - Generates: `BodyCommand(posture=RELAXED, luminance=BRIGHT, hands=OPEN, duration=3.0)`
6. **Motion Translation**:
   - Maps `BRIGHT` → LED intensity 75
   - Maps `OPEN` hands with `RELAXED` posture → hand positions ~60
   - Outputs: `{"led_intensity": 75, "hands": {"left": {"position": 60, "status": "open"}, ...}}`
7. **Virtual Body Update**: Body state updated to match command
8. **Memory Check**: No memory flagged by AI
9. **Notification Check**: User activity timestamp updated (prevents inactivity alerts)
10. **Voice Synthesis**: "Too dark for you, sweetheart? Let me light things up." → WAV file → Frontend playback
11. **Response Return**: Complete state snapshot sent to frontend

### Frontend receives:

```json
{
  "response": "Too dark for you, sweetheart? Let me light things up.",
  "cognitive_state": {
    "goal": "provide_illumination",
    "emotion": "helpful",
    "confidence": 0.9,
    "urgency": 0.5
  },
  "hardware_state": {
    "led_intensity": 75,
    "hands": {"left": {"position": 60, "status": "open"}, ...}
  },
  "body_state": {"posture": "relaxed", "luminance": "bright", ...},
  "mood": {"curiosity": 0.5, "irritation": 0.0, ...}
}
```

**Note**: All steps in this flow are tracked by the monitoring system, recording API response times, LLM inference duration, voice processing time, and any errors encountered. Metrics are available in real-time on the monitoring dashboard (port 8081).

---

## Key Design Principles

### 1. Separation of Concerns

- **Cognitive Layer**: Never mentions hardware primitives, only goals/emotions
- **Behavioral Layer**: Maps cognitive states to abstract body commands
- **Motion Layer**: ONLY layer that knows hardware details (LED values, positions)

### 2. Symbolic vs. Concrete

- All layers above motion use **symbolic states** (Posture.AGGRESSIVE, Luminance.INTENSE)
- Only motion controller converts to **concrete values** (intensity=100, position=0)
- This allows hardware changes without touching AI logic

### 3. Embodiment

- AI reasons about "what I want to do" (illuminate, protect, greet)
- System translates intent into physical expression automatically
- No asterisks, stage directions, or hardware commands in dialogue

### 4. Personality Consistency

- ASR-7 personality enforced at every layer:
  - Cognitive prompt maintains sarcastic/flirty tone (25% friendly, 70% sarcastic, 5% flirtatious)
  - Agent tasks include personality enhancement
  - Memory extraction focuses on relationship with Evan
  - Time awareness adds character-appropriate comments
  - **Mood state influences AI responses**: Curiosity affects verbosity, irritation shortens responses, boredom reduces engagement, attachment increases warmth

### 5. Emergent Behavior

- Mood evolves based on interaction patterns (not directly controlled)
- Behavior selection emerges from utility scores (not hardcoded rules)
- Memory importance judged by AI (not keyword matching)

### 6. Real-time Integration

- Vision continuously updates world state
- Mood continuously evolves with time/interactions
- Voice synthesis async to prevent blocking
- Background monitoring for proactive notifications

---

## Future Enhancement Opportunities

### Hardware Layer

- **Physical Arduino/ESP32 Integration**: Implement `hardware_server.py` to send hardware state to real servos/LEDs
- **Smooth Motion Interpolation**: Enable motion controller's interpolation for gradual transitions
- **Head Tracking**: Implement attention target → head orientation mapping

### Vision Enhancements

- **Face Recognition**: Track individuals by identity, not just "person_1"
- **Gesture Recognition**: Respond to hand waves, thumbs up, etc.
- **Spatial Tracking**: 3D position estimation for entities
- **Scene Understanding**: Use multimodal LLMs for deeper scene comprehension

### Autonomous Agent

- **Multi-Agent Collaboration**: Multiple specialized agents working together
- **Long-Term Project Tracking**: Persistent project goals and progress
- **Self-Improvement**: Agent learns from past task successes/failures
- **External Tool Integration**: API access, database queries, web scraping

### Personalization

- **User Profile Learning**: Adapt to user's communication style and preferences
- **Relationship Dynamics**: Track relationship milestones and inside jokes
- **Context Switching**: Handle multiple conversation threads
- **Proactive Suggestions**: Suggest tasks based on patterns

### Multimodal Expansion

- **Audio Input**: Speech-to-text for voice commands
- **Image Generation**: Create visualizations for concepts
- **Video Understanding**: Process video streams for complex scenarios

### Monitoring & Observability Enhancements

- **Alerting System**: Notifications for performance degradation thresholds
- **Historical Metrics Database**: Persistent storage beyond in-memory (SQLite/PostgreSQL)
- **Grafana/Prometheus Integration**: Industry-standard monitoring dashboards
- **Custom Metric Thresholds**: User-configurable alerts for API latency, error rates
- **Distributed Tracing**: Request correlation across components
- **Performance Profiling**: Automatic detection of bottlenecks

### Discord Bot Enhancements

- **Multi-Server Support**: Per-server conversation context and settings
- **Voice Channel Integration**: Join voice channels to speak audio directly
- **Reaction-Based Interactions**: React to messages for quick responses
- **Discord Slash Command Autocomplete**: Context-aware parameter suggestions
- **Threaded Conversations**: Keep long discussions organized in Discord threads
- **Server-Specific Personalities**: Different behavior per Discord server
- **Role-Based Permissions**: Control who can use certain commands

---

## Developer Notes

### Adding a New Behavior

1. Create class inheriting from `Behavior` in `behavioral_layer.py`
2. Implement `calculate_utility()` with goal/emotion matching
3. Implement `execute()` returning appropriate `BodyCommand`
4. Add to `BehaviorArbiter.behaviors` list
5. Update `describe_behavior_library()` with description

### Adding a New Tool (Autonomous Agent)

1. Implement function with clear signature in appropriate manager
2. Add to `AgentLogic.tools` dictionary in `agent_logic.py`
3. Update agent prompt's tool list with description
4. Test in isolation before integration

### Modifying Personality

Edit `Config.ASSAULTRON_PROMPT` in `config.py`:
- Adjust personality ratios
- Add/remove behavioral guidelines
- Update example dialogue
- Modify memory formation rules

### Debugging

- **Logs**: Check `debug/logs/assaultron.log` for detailed execution traces
- **Behavior History**: `/api/embodied/behavior_history` shows behavior selections
- **State History**: `/api/embodied/state_history` shows body transitions
- **Cognitive Raw Response**: Enable debug logging to see unparsed LLM outputs

---

## Conclusion

The Assaultron Project ASR-7 implements a sophisticated embodied agent architecture that creates a character-driven AI companion with personality, physical presence, and autonomous capabilities. By separating cognitive reasoning from behavioral selection and hardware translation, the system achieves modularity, maintainability, and extensibility while maintaining a consistent personality throughout all interactions.

The architecture successfully bridges the gap between abstract AI reasoning and concrete physical expression, creating an immersive experience where the AI exists as a character with thoughts, emotions, and a body rather than just a text generator.

---

**Document Version**: 1.6
**Last Updated**: 2026-02-17
**Architecture Status**: Production (Embodied Agent v2.0 + Multi-Service Infrastructure + Bidirectional Voice I/O)

**Changelog v1.6** (2026-02-17):
- **Updated File Paths**: Corrected all file paths to reflect new directory structure
  - Audio output: `audio_output/` → `ai-data/audio_output/`
  - Sandbox path: `./sandbox` → `./src/sandbox`
  - Discord bot: `discord/bot.js` → `src/discord/bot.js`
  - Monitoring reports: `report/` → `debug/reports/`
  - Log files: `logs/` → `debug/logs/`
  - Conversation history, memories, mood state: Root → `ai-data/`
  - Chat images: `chat_images/` → `ai-data/chat_images/`
- **Updated Personality Configuration**: Adjusted personality ratio to 25% Friendly, 70% Sarcastic, 5% Flirtatious (from 10/45/45)
- **Added Sandbox Configuration**: Documented `SANDBOX_PATH` environment variable in configuration section

**Changelog v1.5** (2026-02-16):
- **Added Speech-to-Text System**: Full voice input capability using Mistral Voxtral API for real-time transcription
- **Added STT API Endpoints**: 9 new endpoints for transcription control, device management, and real-time event streaming
- **Added Real-time Transcription**: Streaming audio processing with partial deltas and complete phrase transcripts
- **Added Audio Visualization**: RMS volume level calculation at 10Hz with SSE broadcasting for live volume meters
- **Updated Dependencies**: Added mistralai[realtime] and pyaudio packages with platform-specific installation notes
- **Updated System Architecture**: Bidirectional voice communication - TTS output + STT input for natural conversation
- **Added Device Management**: Microphone device enumeration and selection with graceful stream switching

**Changelog v1.4** (2026-02-14):
- **Added Agent Override Check**: Documented new opt-out phrase detection in task detection — users can bypass agent invocation with phrases like "don't use agent", "no agent", "skip agent", etc.

**Changelog v1.3** (2026-02-14):
- **Fixed Memory Limits**: Corrected memories.json description — max 10 via AI-managed path, max 50 via manual add_memory()
- **Fixed Task Detection Keywords**: Replaced incomplete 5-keyword list with actual two-part system (20+ action verbs AND 14+ creation indicators)
- **Added Missing API Endpoints**: Documented /api/memory, /api/debug/last_response, /api/tools/available, /chat_images/<filename>
- **Fixed Vision Capture Rate**: Clarified webcam captures at 30 FPS, object detection processes at ~10 FPS
- **Fixed Voice SSE Attribution**: Corrected voicemanager.py uses callback pattern; Flask translates to SSE in /api/voice/events
- **Added /clear Slash Command**: Documented Discord bot /clear [number] command for message deletion

**Changelog v1.2** (2026-02-13):
- **Added Monitoring & Observability System**: Complete documentation of production-grade metrics collection, live dashboard (port 8081), and performance tracking
- **Added Discord Bot Integration**: Full Discord bot with voice message support, slash commands (/voice, /llm), SSE integration, and FFmpeg audio conversion
- **Added Multi-Service Architecture**: Documented run.py service orchestrator with toggleable services (ASR, Docs, Discord Bot, Monitoring)
- **Updated API Endpoints**: Added /api/voice/events (SSE stream), /api/monitoring/discord_status, and monitoring dashboard endpoints
- **Updated Configuration**: Added Discord bot environment variables (DISCORD_BOT_TOKEN, etc.)
- **Updated Dependencies**: Added Node.js packages (discord.js, axios, eventsource) and FFmpeg system dependency
- **Updated Security Features**: Documented Discord bot security model
- **Updated Data Persistence**: Added monitoring report generation (report/*.md)
- **Updated Future Enhancements**: Added monitoring alerting, Grafana integration, Discord voice channel support, and multi-server context
- **Enhanced Execution Flow**: Added note about monitoring tracking all pipeline steps

**Changelog v1.1** (2026-02-10):
- Corrected memory limits: Long-term memories max 10 (not 50), conversation history max 100
- Moved all LLM and voice configuration to .env for better deployment practices
- Clarified mood state integration: Mood DOES influence AI responses with behavioral guidance
- Confirmed vision uses MediaPipe EfficientDet-Lite0 (not YOLO)
