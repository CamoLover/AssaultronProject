# Assaultron Project ASR-7 - System Architecture

## Overview

The Assaultron Project ASR-7 is an **embodied AI agent system** implementing a behavior-based architecture inspired by robotics subsumption architectures and reactive planning systems. The system goes beyond traditional chatbots by implementing a **virtual body** that translates high-level intentions into physical-like states, creating a more immersive and character-driven interaction model.

**Project Type**: Personal AI companion robot with autonomous task execution capabilities
**Architecture Pattern**: Layered Embodied Agent (Cognitive → Behavioral → Motion)
**Primary Language**: Python 3.9+
**AI Models**: Multi-provider support (Ollama local, Google Gemini, OpenRouter/DeepSeek)
**Voice**: xVAsynth with Fallout 4 Assaultron voice model
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

**Purpose**: TTS (Text-to-Speech) using xVAsynth for character-authentic voice.

**Components**:
- **Server Management**: Starts/stops xVAsynth server (localhost:8008)
- **Model Loading**: Loads Fallout 4 Assaultron voice model (`f4_robot_assaultron.json`)
- **Async Synthesis**: Queue-based audio generation to prevent blocking
- **Real-time Events**: Server-Sent Events (SSE) to notify frontend when audio is ready

**Audio Pipeline**:
```
Dialogue Text → xVAsynth API → WAV File → audio_output/ → Frontend Playback
```

**Implementation Notes**:
- Handles port conflicts and server startup retries
- Monitors server logs via threaded stdout/stderr readers
- Provides fallback for startup failures

---

### Vision System (`vision_system.py`)

**Purpose**: Webcam-based perception layer using MediaPipe for object detection.

**Components**:
- **Object Detection**: MediaPipe EfficientDet-Lite0 (CPU-optimized, fast)
- **Camera Management**: Enumerate, select, start/stop capture
- **Real-time Processing**: Background thread captures frames at ~10 FPS
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
- All operations restricted to `SANDBOX_PATH` directory (default: `./sandbox`)
- Path validation prevents directory traversal attacks
- Command execution sandboxed within workspace

**Operations**:
- File CRUD (create, read, update, delete)
- Folder management
- Command execution (git, npm, python, etc.)
- File existence checks

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
- Uses LLM to classify if message is an actionable task
- Keywords: "create", "make", "write", "research", "build"
- Fallback to keyword matching if LLM fails
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

`config.py` loads these values using `os.getenv()` with sensible defaults.

### Personality Prompt

Contains `ASSAULTRON_PROMPT` - the core system prompt defining ASR-7's personality:
- 10% Friendly, 45% Sarcastic, 45% Flirtatious
- Embodied agent instructions (express goals/emotions, not hardware)
- Vision integration rules
- Time awareness guidelines
- Memory formation guidelines

---

## Data Persistence

### Files Created

**Runtime State**:
- `conversation_history.json` - Conversation exchanges (max 100, last 8 sent to LLM)
- `memories.json` - Long-term core memories (max 10 stored, last 15 sent to LLM, LLM-managed)
- `mood_state.json` - Current mood state (persists across sessions)

**Agent Workspace**:
- `sandbox/.agent_history.json` - Agent task history (last 50 tasks)
- `sandbox/<user_projects>/` - Agent-created files and folders

**Audio Output**:
- `audio_output/*.wav` - Generated voice audio files

**Logs**:
- `logs/assaultron.log` - Main log file (rotating, 10MB max, 5 backups)
- `logs/assaultron_errors.log` - Errors only (rotating, 10MB max, 3 backups)

**Chat Images**:
- `chat_images/*.jpg|png|gif|webp` - User-uploaded image attachments

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

- All agent file operations restricted to `SANDBOX_PATH`
- Path validation prevents directory traversal
- Command execution sandboxed within workspace

### Email Security

- Rate limiting: Configurable (default 10/hour)
- Domain whitelist: `ALLOWED_EMAIL_DOMAINS`
- Only sends if `EMAIL_ENABLED=true`

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

### AI

```
google-generativeai>=0.3.0  # For Gemini support
```

### Optional

- Ollama (local LLM server)
- Brave Search API key (for web search)
- Discord webhook URLs (for notifications)

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
  - Cognitive prompt maintains sarcastic/flirty tone (10% friendly, 45% sarcastic, 45% flirtatious)
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

- **Logs**: Check `logs/assaultron.log` for detailed execution traces
- **Behavior History**: `/api/embodied/behavior_history` shows behavior selections
- **State History**: `/api/embodied/state_history` shows body transitions
- **Cognitive Raw Response**: Enable debug logging to see unparsed LLM outputs

---

## Conclusion

The Assaultron Project ASR-7 implements a sophisticated embodied agent architecture that creates a character-driven AI companion with personality, physical presence, and autonomous capabilities. By separating cognitive reasoning from behavioral selection and hardware translation, the system achieves modularity, maintainability, and extensibility while maintaining a consistent personality throughout all interactions.

The architecture successfully bridges the gap between abstract AI reasoning and concrete physical expression, creating an immersive experience where the AI exists as a character with thoughts, emotions, and a body rather than just a text generator.

---

**Document Version**: 1.1
**Last Updated**: 2026-02-10
**Architecture Status**: Production (Embodied Agent v2.0)

**Changelog v1.1**:
- Corrected memory limits: Long-term memories max 10 (not 50), conversation history max 100
- Moved all LLM and voice configuration to .env for better deployment practices
- Clarified mood state integration: Mood DOES influence AI responses with behavioral guidance
- Confirmed vision uses MediaPipe EfficientDet-Lite0 (not YOLO)
