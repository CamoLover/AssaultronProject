# Assaultron ASR-7 - Visual Architecture Guide

A comprehensive visual guide to the Assaultron Project's embodied AI architecture using interactive diagrams.

---

## Multi-Service Architecture

```mermaid
graph TB
    subgraph "run.py - Service Orchestrator"
        RunPy[run.py Launcher]
        Flags{Configuration Flags}
    end

    subgraph "Service 1: Monitoring Dashboard - Port 8081"
        MonDash[monitoring_dashboard.py]
        MonService[monitoring_service.py<br/>MetricsCollector]
        DashUI[Dashboard UI<br/>Live Charts & Stats]
    end

    subgraph "Service 2: Discord Bot - Node.js"
        DiscordBot[discord/bot.js]
        DiscordAPI[Discord API<br/>Gateway Connection]
        SSEListener[SSE Event Listener<br/>/api/voice/events]
        FFmpeg[FFmpeg Converter<br/>WAV → OGG Opus]
    end

    subgraph "Service 3: ASR-7 AI Interface - Port 8080"
        MainApp[main.py<br/>EmbodiedAssaultronCore]
        CognitiveLayer[Cognitive Layer]
        BehavioralLayer[Behavioral Layer]
        VoiceSystem[Voice System]
        VisionSystem[Vision System]
    end

    subgraph "Service 4: Documentation - Port 8000"
        DocsServer[HTTP Server<br/>SimpleHTTPRequestHandler]
        DocsHTML[docs/**/*.html]
    end

    subgraph "External Systems"
        DiscordServers[Discord Servers]
        Webcam[Webcam Device]
        xVAsynth[xVAsynth TTS]
    end

    RunPy --> Flags
    Flags -->|START_MONITORING=True| MonDash
    Flags -->|START_DISCORD_BOT=True| DiscordBot
    Flags -->|START_ASR=True| MainApp
    Flags -->|START_DOCS=True| DocsServer

    MonDash --> MonService
    MonService --> DashUI

    DiscordBot --> DiscordAPI
    DiscordBot --> SSEListener
    DiscordBot --> FFmpeg
    DiscordAPI <--> DiscordServers

    SSEListener --> MainApp
    DiscordBot -->|POST /api/chat| MainApp
    DiscordBot -->|POST /api/monitoring/discord_status| MainApp

    MainApp --> CognitiveLayer
    MainApp --> BehavioralLayer
    MainApp --> VoiceSystem
    MainApp --> VisionSystem
    MainApp -->|Record Metrics| MonService

    VoiceSystem --> xVAsynth
    VisionSystem --> Webcam

    DocsServer --> DocsHTML

    classDef orchestrator fill:#fce4ec,stroke:#c2185b,stroke-width:3px
    classDef service fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef external fill:#f3e5f5,stroke:#4a148c,stroke-width:2px

    class RunPy,Flags orchestrator
    class MonDash,MonService,DashUI,DiscordBot,MainApp,DocsServer service
    class DiscordServers,Webcam,xVAsynth,DiscordAPI external
```

---

## Monitoring System Architecture

```mermaid
graph TB
    subgraph "Metrics Sources"
        APICall[API Endpoints<br/>/api/chat, /api/voice, etc.]
        VoiceSynth[Voice Synthesis<br/>xVAsynth]
        LLMRequest[LLM Inference<br/>Ollama/Gemini/OpenRouter]
        SystemDelay[System Components<br/>Cognitive/Behavioral/Motion]
        Errors[Error Handlers<br/>try/except blocks]
    end

    subgraph "MetricsCollector - Thread-Safe"
        Collector[MetricsCollector Singleton]
        Lock[threading.Lock]

        subgraph "Metrics Storage (deque maxlen=1000)"
            APIMetrics[api_responses<br/>endpoint, duration, status]
            VoiceMetrics[voice_processing<br/>text_length, duration, success]
            LLMMetrics[llm_requests<br/>model, tokens, duration]
            DelayMetrics[system_delays<br/>component, duration]
            ErrorMetrics[errors<br/>timestamp, component, message]
        end

        subgraph "Counters"
            TotalMsgs[total_messages]
            TotalAPIs[total_api_calls]
            TotalVoice[total_voice_generated]
            TotalTokens[total_llm_tokens]
            TotalErrors[total_errors]
        end

        subgraph "System Status"
            AIActive[ai_active: bool]
            VoiceEnabled[voice_enabled: bool]
            DiscordActive[discord_bot_active: bool]
            CurrentReqs[current_requests: int]
        end
    end

    subgraph "Monitoring Dashboard - Port 8081"
        FlaskApp[Flask App<br/>monitoring_dashboard.py]

        subgraph "API Endpoints"
            StatsAPI[GET /api/stats]
            StreamSSE[GET /api/stream<br/>SSE every 1s]
            MetricsAPI[GET /api/metrics/:name]
            ExportAPI[GET /api/export]
        end

        subgraph "Dashboard UI"
            StatusPanel[Live Status Panel<br/>Uptime, Service Indicators]
            ChartsPanel[Performance Charts<br/>Chart.js Visualizations]
            ErrorsPanel[Recent Errors Log<br/>Last 50 errors]
            DarkMode[Dark Mode Toggle<br/>localStorage]
        end
    end

    subgraph "Report Generation"
        ShutdownHook[atexit Hook<br/>in run.py]
        ReportGen[generate_shutdown_report]
        MarkdownFile[report/monitoring_report_*.md]
    end

    APICall -->|record_api_response| Collector
    VoiceSynth -->|record_voice_processing| Collector
    LLMRequest -->|record_llm_request| Collector
    SystemDelay -->|record_system_delay| Collector
    Errors -->|record_error| Collector

    Collector --> Lock
    Lock --> APIMetrics
    Lock --> VoiceMetrics
    Lock --> LLMMetrics
    Lock --> DelayMetrics
    Lock --> ErrorMetrics
    Lock --> TotalMsgs
    Lock --> TotalAPIs
    Lock --> TotalVoice
    Lock --> TotalTokens
    Lock --> TotalErrors
    Lock --> AIActive
    Lock --> VoiceEnabled
    Lock --> DiscordActive
    Lock --> CurrentReqs

    FlaskApp --> StatsAPI
    FlaskApp --> StreamSSE
    FlaskApp --> MetricsAPI
    FlaskApp --> ExportAPI

    StatsAPI --> StatusPanel
    StreamSSE --> ChartsPanel
    MetricsAPI --> ChartsPanel
    ExportAPI --> ReportGen

    StatusPanel --> DarkMode
    ChartsPanel --> ErrorsPanel

    ShutdownHook --> ReportGen
    ReportGen --> MarkdownFile

    Collector --> StatsAPI
    Collector --> StreamSSE

    classDef source fill:#e3f2fd,stroke:#1565c0
    classDef storage fill:#fff3e0,stroke:#ef6c00
    classDef dashboard fill:#e8f5e9,stroke:#2e7d32
    classDef report fill:#f3e5f5,stroke:#4a148c

    class APICall,VoiceSynth,LLMRequest,SystemDelay,Errors source
    class Collector,Lock,APIMetrics,VoiceMetrics,LLMMetrics,DelayMetrics,ErrorMetrics,TotalMsgs,TotalAPIs,TotalVoice,TotalTokens,TotalErrors,AIActive,VoiceEnabled,DiscordActive,CurrentReqs storage
    class FlaskApp,StatsAPI,StreamSSE,MetricsAPI,ExportAPI,StatusPanel,ChartsPanel,ErrorsPanel,DarkMode dashboard
    class ShutdownHook,ReportGen,MarkdownFile report
```

---

## Discord Bot Integration & Voice Messages

```mermaid
sequenceDiagram
    actor DiscordUser
    participant Discord as Discord Servers
    participant Bot as discord/bot.js
    participant SSE as SSE Connection<br/>/api/voice/events
    participant AI as ASR-7 AI Server<br/>Port 8080
    participant xVA as xVAsynth
    participant FFmpeg as FFmpeg Converter
    participant CDN as Discord CDN

    Note over DiscordUser,CDN: Initialization
    Bot->>Discord: Login with DISCORD_BOT_TOKEN
    Discord-->>Bot: Bot online
    Bot->>AI: POST /api/monitoring/discord_status {active: true}

    Note over DiscordUser,CDN: User activates voice via slash command
    DiscordUser->>Discord: /voice activate
    Discord->>Bot: Slash command interaction
    Bot->>AI: POST /api/voice/start
    AI->>xVA: Start xVAsynth server
    xVA-->>AI: Model loaded
    AI-->>Bot: Voice system active
    Bot->>SSE: Connect to /api/voice/events
    Bot->>Discord: ✅ Voice activated! (embed)

    Note over DiscordUser,CDN: Regular chat message
    DiscordUser->>Discord: @ASR-7 Hey there!
    Discord->>Bot: Message event
    Bot->>Bot: Reset notification counter
    Bot->>AI: POST /api/chat {message, source: "discord"}

    AI->>AI: Process message through<br/>Cognitive → Behavioral → Motion
    AI->>AI: Generate dialogue response
    AI->>xVA: Synthesize speech async
    xVA->>xVA: Generate WAV file
    xVA-->>AI: audio_output/response.wav

    AI->>SSE: Emit "audio_ready" event<br/>{filename, url}
    SSE-->>Bot: Event received

    Note over DiscordUser,CDN: Voice message conversion & upload
    Bot->>AI: GET /api/voice/audio/response.wav
    AI-->>Bot: WAV file bytes
    Bot->>Bot: Save temp_voice.wav

    Bot->>FFmpeg: Check ffmpeg availability
    FFmpeg-->>Bot: Available

    Bot->>FFmpeg: Convert WAV → OGG Opus<br/>48kHz, 64k bitrate
    FFmpeg-->>Bot: temp_voice.ogg

    Bot->>FFmpeg: Extract metadata<br/>duration via ffprobe
    FFmpeg-->>Bot: duration, waveform data

    Bot->>Discord: Request upload URL
    Discord-->>Bot: Upload URL + file ID

    Bot->>CDN: PUT upload OGG file
    CDN-->>Bot: Upload complete

    Bot->>Discord: POST message with<br/>IS_VOICE_MESSAGE flag<br/>+ metadata (duration, waveform)
    Discord->>DiscordUser: Voice message appears

    Bot->>Bot: Cleanup temp files

    AI-->>Bot: JSON response {dialogue, states}
    Bot->>Discord: "Hey there!" (text fallback)

    Note over DiscordUser,CDN: LLM provider change
    DiscordUser->>Discord: /llm change gemini
    Discord->>Bot: Slash command
    Bot->>AI: POST /api/settings/provider {provider: "gemini"}
    AI-->>Bot: Provider switched
    Bot->>Discord: ✅ LLM provider: gemini-2.5-flash

    Note over DiscordUser,CDN: Agent task completion broadcast
    AI->>AI: Agent completes task
    AI->>SSE: Emit "agent_completion" event
    SSE-->>Bot: Agent result message
    Bot->>Discord: 🤖 Task complete: [result]
```

---

## System Overview

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[Web Interface]
        WS[WebSocket/SSE Events]
    end

    subgraph "Multi-Channel Input"
        WebInput[Web UI Messages]
        DiscordInput[Discord Bot Messages]
    end

    subgraph "Flask API Layer - Port 8080"
        API[REST API Endpoints]
        RateLimit[Rate Limiter]
        Auth[Authentication]
    end

    subgraph "Core Orchestrator"
        Main[EmbodiedAssaultronCore]
    end

    subgraph "Cognitive Layer"
        CogEngine[Cognitive Engine]
        LLM[LLM Provider<br/>Ollama/Gemini/OpenRouter]
        Memory[Long-term Memory]
        History[Conversation History]
    end

    subgraph "Behavioral Layer"
        Arbiter[Behavior Arbiter]
        Behaviors[Behavior Library<br/>Intimidate/Greet/Protect/etc]
    end

    subgraph "Virtual World"
        Body[Body State]
        World[World State]
        Mood[Mood State]
    end

    subgraph "Motion Layer"
        Motion[Motion Controller]
        Hardware[Hardware Translation]
    end

    subgraph "Perception Systems"
        Vision[Vision System<br/>MediaPipe]
        Time[Time Awareness]
    end

    subgraph "Input/Output Systems"
        Voice[Voice Output<br/>xVAsynth TTS]
        STT[Voice Input<br/>Mistral Voxtral STT]
        Notify[Notification Manager<br/>Discord Webhooks]
    end

    subgraph "Autonomous Systems"
        Agent[Agent Logic<br/>ReAct Pattern]
        Sandbox[Sandbox Manager]
        Tools[Tool Registry]
    end

    subgraph "Monitoring & Observability - Port 8081"
        Monitor[Monitoring Service<br/>MetricsCollector]
        Dashboard[Monitoring Dashboard<br/>Live UI]
    end

    subgraph "External Integrations"
        DiscordBot[Discord Bot<br/>Node.js]
        DiscordServers[Discord Servers]
    end

    UI --> WebInput
    WebInput --> API
    DiscordBot --> DiscordInput
    DiscordInput --> API
    API --> Main
    Main --> CogEngine
    Main --> Arbiter
    Main --> Vision
    Main --> Voice
    Main --> STT
    Main --> Notify
    Main --> Agent

    STT --> Main

    CogEngine --> LLM
    CogEngine --> Memory
    CogEngine --> History

    Arbiter --> Behaviors
    Behaviors --> Motion

    Vision --> World
    Time --> CogEngine

    Body --> CogEngine
    World --> CogEngine
    Mood --> CogEngine

    Motion --> Hardware

    Agent --> Sandbox
    Agent --> Tools

    Voice --> WS
    Voice -->|SSE events| DiscordBot
    DiscordBot <--> DiscordServers

    Main -->|Record metrics| Monitor
    API -->|Record metrics| Monitor
    Voice -->|Record metrics| Monitor
    LLM -->|Record metrics| Monitor
    Monitor --> Dashboard

    DiscordBot -->|POST /api/monitoring/discord_status| API

    classDef cognitive fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef behavioral fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef perception fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef output fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef monitoring fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef external fill:#e0f2f1,stroke:#00695c,stroke-width:2px

    class CogEngine,LLM,Memory,History cognitive
    class Arbiter,Behaviors,Motion behavioral
    class Vision,Time perception
    class Voice,Notify output
    class Monitor,Dashboard monitoring
    class DiscordBot,DiscordServers external
```

---

## Message Processing Pipeline

```mermaid
sequenceDiagram
    actor User
    participant API as Flask API
    participant Main as Core Orchestrator
    participant Vision as Vision System
    participant World as Virtual World
    participant Cog as Cognitive Engine
    participant LLM as LLM Provider
    participant Behav as Behavior Arbiter
    participant Motion as Motion Controller
    participant Voice as Voice System
    participant Notify as Notifications

    User->>API: POST /api/chat
    API->>Main: process_message()

    Main->>Main: Analyze message for world cues
    Main->>World: update_world(threats, environment)
    Main->>World: update_mood(message, patterns)

    alt Vision Enabled
        Main->>Vision: get_entities()
        Vision-->>Main: detected_entities
        Main->>World: update_world(entities)
    end

    Main->>World: get_current_state()
    World-->>Main: body_state, world_state, mood_state

    Main->>Cog: process_input(message, states, vision)
    Cog->>LLM: Enhanced prompt + context
    LLM-->>Cog: JSON response
    Cog-->>Main: CognitiveState

    Main->>Behav: select_and_execute(cognitive_state)
    Behav->>Behav: Calculate utilities
    Behav-->>Main: BodyCommand

    Main->>Motion: apply_body_command()
    Motion-->>Main: HardwareState

    Main->>World: update_body(body_command)

    alt Memory flagged
        Main->>Cog: manage_memory()
    end

    Main->>Notify: check_notifications()

    alt Voice Enabled
        Main->>Voice: synthesize_async(dialogue)
        Voice-->>User: SSE audio ready event
    end

    Main-->>API: Complete response
    API-->>User: JSON response
```

---

## Cognitive Layer Architecture

```mermaid
graph LR
    subgraph "Input Processing"
        UserMsg[User Message]
        WorldCtx[World Context]
        BodyCtx[Body State]
        MoodCtx[Mood State]
        VisionCtx[Vision Data]
        TimeCtx[Time Context]
        MemoryCtx[Memory Summary]
        History[Conversation History]
        Image[Image Input]
    end

    subgraph "Cognitive Engine"
        Formatter[Prompt Formatter]
        Provider{LLM Provider}
        Parser[JSON Parser]
        Validator[Response Validator]
    end

    subgraph "LLM Providers"
        Ollama[Ollama<br/>gemma3:4b<br/>Local]
        Gemini[Google Gemini<br/>gemini-2.5-flash<br/>Multimodal]
        OpenRouter[OpenRouter<br/>DeepSeek-V3.2<br/>Cloud]
    end

    subgraph "Output"
        CogState[Cognitive State<br/>goal, emotion, confidence,<br/>urgency, dialogue, memory]
    end

    UserMsg --> Formatter
    WorldCtx --> Formatter
    BodyCtx --> Formatter
    MoodCtx --> Formatter
    VisionCtx --> Formatter
    TimeCtx --> Formatter
    MemoryCtx --> Formatter
    History --> Formatter
    Image --> Formatter

    Formatter --> Provider

    Provider -->|LLM_PROVIDER=ollama| Ollama
    Provider -->|LLM_PROVIDER=gemini| Gemini
    Provider -->|LLM_PROVIDER=openrouter| OpenRouter

    Ollama --> Parser
    Gemini --> Parser
    OpenRouter --> Parser

    Parser --> Validator
    Validator --> CogState

    classDef input fill:#e3f2fd,stroke:#1565c0
    classDef processing fill:#fff3e0,stroke:#ef6c00
    classDef output fill:#e8f5e9,stroke:#2e7d32

    class UserMsg,WorldCtx,BodyCtx,MoodCtx,VisionCtx,TimeCtx,MemoryCtx,History,Image input
    class Formatter,Provider,Parser,Validator processing
    class CogState output
```

---

## Behavioral Layer - Utility-Based Selection

```mermaid
graph TB
    subgraph "Input"
        CogState[Cognitive State<br/>goal, emotion, confidence, urgency]
        BodyState[Current Body State]
    end

    subgraph "Behavior Library"
        Intimidate[IntimidateBehavior<br/>hostile, aggressive]
        Greet[FriendlyGreetBehavior<br/>greet, friendly]
        Alert[AlertScanBehavior<br/>investigate, alert]
        Idle[RelaxedIdleBehavior<br/>idle, neutral]
        Curious[CuriousExploreBehavior<br/>explore, curious]
        Protect[ProtectiveBehavior<br/>protect, concerned]
        Playful[PlayfulBehavior<br/>play, happy]
        Illuminate[IlluminateBehavior<br/>provide light]
    end

    subgraph "Behavior Arbiter"
        Calc[Utility Calculator]
        Select[Behavior Selector]
    end

    subgraph "Output"
        BodyCmd[Body Command<br/>posture, luminance,<br/>hands, duration]
    end

    CogState --> Calc
    BodyState --> Calc

    Calc --> Intimidate
    Calc --> Greet
    Calc --> Alert
    Calc --> Idle
    Calc --> Curious
    Calc --> Protect
    Calc --> Playful
    Calc --> Illuminate

    Intimidate -->|utility: 0.0-1.0+| Select
    Greet -->|utility: 0.0-1.0+| Select
    Alert -->|utility: 0.0-1.0+| Select
    Idle -->|utility: 0.0-1.0+| Select
    Curious -->|utility: 0.0-1.0+| Select
    Protect -->|utility: 0.0-1.0+| Select
    Playful -->|utility: 0.0-1.0+| Select
    Illuminate -->|utility: 0.0-1.0+| Select

    Select -->|Highest utility| BodyCmd

    classDef cognitive fill:#e1f5ff,stroke:#01579b
    classDef behavior fill:#fff3e0,stroke:#e65100
    classDef output fill:#c8e6c9,stroke:#2e7d32

    class CogState cognitive
    class Intimidate,Greet,Alert,Idle,Curious,Protect,Playful,Illuminate behavior
    class BodyCmd output
```

---

## Virtual World State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle

    state "Body States" as BodyStates {
        Idle --> Alert: threat detected
        Idle --> Relaxed: friendly interaction
        Idle --> Curious: investigation needed

        Alert --> Aggressive: hostility
        Alert --> Idle: threat cleared

        Aggressive --> Alert: de-escalation
        Aggressive --> Idle: resolution

        Relaxed --> Idle: neutral state
        Relaxed --> Curious: interest piqued

        Curious --> Alert: concern raised
        Curious --> Relaxed: satisfied
        Curious --> Idle: interest fades
    }

    state "Mood Evolution" as MoodStates {
        state "Curiosity" as Curiosity {
            Low_Curiosity --> High_Curiosity: questions asked
            High_Curiosity --> Low_Curiosity: time decay
        }

        state "Irritation" as Irritation {
            Low_Irritation --> High_Irritation: spam/short messages
            High_Irritation --> Low_Irritation: time decay
        }

        state "Boredom" as Boredom {
            Low_Boredom --> High_Boredom: no interaction
            High_Boredom --> Low_Boredom: engagement
        }

        state "Attachment" as Attachment {
            Low_Attachment --> High_Attachment: interactions++
            High_Attachment --> Medium_Attachment: long gaps
        }
    }

    state "World Perception" as WorldStates {
        Normal_Environment --> Dark_Environment: "dark" detected
        Normal_Environment --> Bright_Environment: "bright" detected

        No_Threat --> Low_Threat: minor concern
        Low_Threat --> Medium_Threat: weapon detected
        Medium_Threat --> High_Threat: multiple threats
        High_Threat --> No_Threat: cleared
    }
```

---

## Motion Controller - Symbolic to Hardware Translation

```mermaid
graph LR
    subgraph "Symbolic Body Command"
        Posture[Posture<br/>IDLE/ALERT/AGGRESSIVE/<br/>RELAXED/CURIOUS]
        Luminance[Luminance<br/>DIM/SOFT/NORMAL/<br/>BRIGHT/INTENSE]
        Hands[Hand States<br/>CLOSED/RELAXED/<br/>OPEN/POINTING]
    end

    subgraph "Motion Controller"
        LumMap[Luminance Mapper]
        HandMap[Hand Position Mapper]
        PostureMap[Posture Modifier]
        Safety[Safety Constraints]
    end

    subgraph "Hardware Values"
        LED[LED Intensity<br/>0-100]
        LeftHand[Left Hand Position<br/>0-100]
        RightHand[Right Hand Position<br/>0-100]
    end

    subgraph "Hardware Output"
        HW["Hardware State JSON<br/>led_intensity, hands"]
    end

    Posture --> PostureMap
    Luminance --> LumMap
    Hands --> HandMap

    LumMap -->|DIM=10, SOFT=35,<br/>NORMAL=50, BRIGHT=75,<br/>INTENSE=100| LED

    HandMap --> Safety
    PostureMap --> Safety

    Safety --> LeftHand
    Safety --> RightHand

    LED --> HW
    LeftHand --> HW
    RightHand --> HW

    classDef symbolic fill:#e1f5ff,stroke:#01579b
    classDef hardware fill:#ffebee,stroke:#c62828

    class Posture,Luminance,Hands symbolic
    class LED,LeftHand,RightHand,HW hardware
```

---

## Vision System Pipeline

```mermaid
graph TB
    subgraph "Camera Input"
        Webcam[Webcam Device]
        Frame[Raw Frame Capture<br/>~10 FPS]
    end

    subgraph "Vision Processing"
        MediaPipe[MediaPipe<br/>EfficientDet-Lite0]
        Detect[Object Detection]
        Filter[Confidence Filter<br/>threshold: 0.5]
    end

    subgraph "Entity Tracking"
        Entities[Detected Entities<br/>person, cup, laptop,<br/>knife, etc.]
        Threat[Threat Assessment<br/>weapon detection]
        Scene[Scene Description<br/>Generator]
    end

    subgraph "World Integration"
        WorldUpdate[World State Update]
        CogPrompt[Cognitive Prompt<br/>Enhancement]
    end

    subgraph "Outputs"
        AnnotatedFrame[Annotated Frame<br/>for UI Display]
        RawFrame[Raw Frame B64<br/>for Multimodal LLM]
        EntityList[Entity List JSON]
    end

    Webcam --> Frame
    Frame --> MediaPipe
    MediaPipe --> Detect
    Detect --> Filter

    Filter --> Entities
    Entities --> Threat
    Entities --> Scene

    Threat --> WorldUpdate
    Scene --> CogPrompt
    Entities --> WorldUpdate

    Frame --> AnnotatedFrame
    Frame --> RawFrame
    Entities --> EntityList

    classDef input fill:#e3f2fd,stroke:#1565c0
    classDef processing fill:#fff3e0,stroke:#ef6c00
    classDef output fill:#e8f5e9,stroke:#2e7d32

    class Webcam,Frame input
    class MediaPipe,Detect,Filter,Entities,Threat,Scene processing
    class AnnotatedFrame,RawFrame,EntityList output
```

---

## Autonomous Agent System

```mermaid
graph TB
    subgraph "Task Detection"
        UserMsg[User Message]
        Detector[Task Detector<br/>LLM Classifier]
        Keywords[Keyword Fallback<br/>create/make/build]
    end

    subgraph "ReAct Loop"
        Think[Thought<br/>Analyze Situation]
        Act[Action<br/>Execute Tool]
        Observe[Observation<br/>Process Result]
        Check{Task Complete?}
    end

    subgraph "Tool Registry"
        FileOps[File Operations<br/>create/edit/read/delete]
        SysOps[System Operations<br/>run_command]
        WebOps[Web Operations<br/>web_search]
        EmailOps[Email Operations<br/>send/read]
        GitOps[Git Operations<br/>commit/push/pull]
    end

    subgraph "Sandbox Security"
        PathValidate[Path Validation]
        SandboxDir[Sandbox Directory<br/>./sandbox/]
        CommandSandbox[Command Sandboxing]
    end

    subgraph "Output"
        Result[Final Answer]
        History[Agent History<br/>.agent_history.json]
    end

    UserMsg --> Detector
    Detector --> Think
    Keywords --> Think

    Think --> Act
    Act --> FileOps
    Act --> SysOps
    Act --> WebOps
    Act --> EmailOps
    Act --> GitOps

    FileOps --> PathValidate
    PathValidate --> SandboxDir
    SysOps --> CommandSandbox

    SandboxDir --> Observe
    CommandSandbox --> Observe
    WebOps --> Observe
    EmailOps --> Observe
    GitOps --> Observe

    Observe --> Check
    Check -->|No, max 30 iter| Think
    Check -->|Yes| Result

    Result --> History

    classDef input fill:#e3f2fd,stroke:#1565c0
    classDef process fill:#fff3e0,stroke:#ef6c00
    classDef security fill:#ffebee,stroke:#c62828
    classDef output fill:#e8f5e9,stroke:#2e7d32

    class UserMsg input
    class Think,Act,Observe,Check process
    class PathValidate,SandboxDir,CommandSandbox security
    class Result,History output
```

---

## Voice System Architecture

```mermaid
sequenceDiagram
    participant Core as Core System
    participant Voice as Voice Manager
    participant xVA as xVAsynth Server
    participant Queue as Audio Queue
    participant FS as File System
    participant SSE as SSE Events
    participant UI as Frontend

    Note over Core,UI: Initialization
    Core->>Voice: start_voice_system()
    Voice->>xVA: Start server (localhost:8008)
    xVA-->>Voice: Server ready
    Voice->>xVA: Load f4_robot_assaultron model
    xVA-->>Voice: Model loaded

    Note over Core,UI: Speech Synthesis
    Core->>Voice: synthesize_async(dialogue)
    Voice->>Queue: Add to queue

    Queue->>xVA: POST /synthesize
    xVA->>xVA: Generate WAV
    xVA-->>Queue: Audio data

    Queue->>FS: Save to audio_output/
    FS-->>Queue: File saved

    Queue->>SSE: Emit audio_ready event
    SSE-->>UI: filename, timestamp

    UI->>Voice: GET /api/voice/audio/filename
    Voice-->>UI: WAV file stream
    UI->>UI: Play audio
```

---

## Speech-to-Text System Architecture

```mermaid
sequenceDiagram
    participant User as User (Microphone)
    participant PyAudio as PyAudio Capture
    participant STT as STT Manager
    participant Mistral as Mistral Voxtral API
    participant SSE as SSE Events
    participant UI as Frontend UI

    Note over User,UI: Initialization
    User->>UI: Click "Start STT"
    UI->>STT: POST /api/stt/start
    STT->>PyAudio: Open audio stream (16kHz, mono)
    PyAudio-->>STT: Stream ready
    STT->>Mistral: Create transcription session
    Mistral-->>STT: Session created
    STT->>SSE: Emit transcription_started
    SSE-->>UI: Status update

    Note over User,UI: Real-time Transcription
    loop Every 480ms
        User->>PyAudio: Speak into microphone
        PyAudio->>STT: Audio chunk (PCM 16-bit)
        STT->>STT: Calculate RMS volume
        STT->>SSE: Emit audio_level (0-100%)
        SSE-->>UI: Update volume visualizer
        STT->>Mistral: Stream audio chunk
        Mistral->>Mistral: Process audio
        Mistral-->>STT: Text delta
        STT->>STT: Accumulate transcript
        STT->>SSE: Emit transcription_partial
        SSE-->>UI: Display partial text
    end

    Note over User,UI: Phrase Complete
    User->>PyAudio: Pause speaking
    Mistral-->>STT: TranscriptionStreamDone
    STT->>SSE: Emit transcription_complete
    SSE-->>UI: Full transcript available
    UI->>UI: Auto-send to chat (if enabled)

    Note over User,UI: Stop Transcription
    User->>UI: Click "Stop STT"
    UI->>STT: POST /api/stt/stop
    STT->>PyAudio: Close audio stream
    STT->>SSE: Emit transcription_stopped
    SSE-->>UI: Status update
```

---

## Notification System Flow

```mermaid
graph TB
    subgraph "Trigger Sources"
        Inactivity[Inactivity Timer<br/>5-30 min]
        Threat[Vision Threat Detection]
        Manual[Manual Request]
        NeedsAttention[AI needs_attention Flag]
    end

    subgraph "Notification Manager"
        Check[Check Triggers]
        RateLimit[Rate Limiter<br/>min 30s between]
        WaitingFlag{User Response<br/>Pending?}
        Generate[Generate Message<br/>via Cognitive Engine]
    end

    subgraph "Discord Webhook"
        Format[Format Webhook Payload]
        Send[POST to Discord]
    end

    subgraph "State Management"
        UpdateTime[Update Last Notification]
        SetWaiting[Set Waiting Flag]
        ResetWaiting[Reset on User Activity]
    end

    Inactivity --> Check
    Threat --> Check
    Manual --> Check
    NeedsAttention --> Check

    Check --> RateLimit
    RateLimit --> WaitingFlag

    WaitingFlag -->|Not Waiting| Generate
    WaitingFlag -->|Waiting| Check

    Generate --> Format
    Format --> Send

    Send --> UpdateTime
    UpdateTime --> SetWaiting

    ResetWaiting --> Check

    classDef trigger fill:#e3f2fd,stroke:#1565c0
    classDef process fill:#fff3e0,stroke:#ef6c00
    classDef output fill:#e8f5e9,stroke:#2e7d32

    class Inactivity,Threat,Manual,NeedsAttention trigger
    class Check,RateLimit,WaitingFlag,Generate process
    class Format,Send output
```

---

## Data Persistence Layer

```mermaid
graph LR
    subgraph "Runtime State Files"
        ConvHist[conversation_history.json<br/>Max 100, Last 8 to LLM]
        Memories[memories.json<br/>Max 10, Last 15 to LLM<br/>LLM-managed]
        MoodFile[mood_state.json<br/>Persists across sessions]
    end

    subgraph "Agent Workspace"
        AgentHist[.agent_history.json<br/>Last 50 tasks]
        UserProjects[User Projects<br/>sandbox/**/*]
    end

    subgraph "Audio Output"
        AudioFiles[audio_output/*.wav<br/>Generated speech]
    end

    subgraph "Logs"
        MainLog[logs/assaultron.log<br/>Rotating 10MB, 5 backups]
        ErrorLog[logs/assaultron_errors.log<br/>Rotating 10MB, 3 backups]
    end

    subgraph "User Uploads"
        ChatImages[chat_images/*<br/>jpg/png/gif/webp]
    end

    subgraph "Core System"
        CogEngine[Cognitive Engine]
        AgentLogic[Agent Logic]
        VoiceSystem[Voice System]
        VirtualWorld[Virtual World]
        Logger[Logger]
        API[Flask API]
    end

    CogEngine -->|read/write| ConvHist
    CogEngine -->|read/write| Memories
    VirtualWorld -->|read/write| MoodFile

    AgentLogic -->|read/write| AgentHist
    AgentLogic -->|read/write| UserProjects

    VoiceSystem -->|write| AudioFiles

    Logger -->|write| MainLog
    Logger -->|write| ErrorLog

    API -->|read| ChatImages

    classDef state fill:#e1f5ff,stroke:#01579b
    classDef workspace fill:#fff3e0,stroke:#e65100
    classDef media fill:#f3e5f5,stroke:#4a148c
    classDef logs fill:#ffebee,stroke:#c62828

    class ConvHist,Memories,MoodFile state
    class AgentHist,UserProjects workspace
    class AudioFiles,ChatImages media
    class MainLog,ErrorLog logs
```

---

## REST API Endpoint Map

```mermaid
graph TB
    subgraph "Chat & Core"
        Chat[POST /api/chat<br/>Rate: 100/min]
        Upload[POST /api/chat/upload_image]
        Status[GET /api/status]
        Logs[GET /api/logs]
        History[GET /api/history]
        ClearHist[POST /api/history/clear]
    end

    subgraph "Embodied Agent"
        VirtualWorld[GET /api/embodied/virtual_world]
        BodyState[GET /api/embodied/body_state]
        WorldState[GET /api/embodied/world_state]
        MoodState[GET/POST /api/embodied/mood_state]
        MoodHistory[GET /api/embodied/mood_history]
        BehaviorHist[GET /api/embodied/behavior_history]
        StateHist[GET /api/embodied/state_history]
    end

    subgraph "Memory"
        GetMem[GET /api/embodied/long_term_memories]
        AddMem[POST /api/embodied/long_term_memories/add]
        EditMem[POST /api/embodied/long_term_memories/edit]
        DelMem[POST /api/embodied/long_term_memories/delete]
    end

    subgraph "Hardware"
        HWState[GET /api/hardware]
        LED[POST /api/hardware/led]
        Hands[POST /api/hardware/hands]
    end

    subgraph "Voice & Speech"
        VoiceStart[POST /api/voice/start]
        VoiceStop[POST /api/voice/stop]
        Speak[POST /api/voice/speak]
        VoiceStatus[GET /api/voice/status<br/>Exempt rate limit]
        Audio["GET /api/voice/audio/:file"]
        VoiceEvents[GET /api/voice/events<br/>SSE Stream]

        SttStart[POST /api/stt/start]
        SttStop[POST /api/stt/stop]
        SttPause[POST /api/stt/pause]
        SttResume[POST /api/stt/resume]
        SttStatus[GET /api/stt/status]
        SttEvents[GET /api/stt/events<br/>SSE Stream]
        SttDevices[GET /api/stt/devices]
        SttSetDevice[POST /api/stt/set_device]
        SttClear[POST /api/stt/clear]
    end

    subgraph "Vision"
        VisionStatus[GET /api/vision/status]
        Cameras[GET /api/vision/cameras]
        SelectCam[POST /api/vision/select_camera]
        StartVision[POST /api/vision/start]
        StopVision[POST /api/vision/stop]
        Frame[GET /api/vision/frame]
        Entities[GET /api/vision/entities]
    end

    subgraph "Autonomous Agent"
        AgentTask[POST /api/agent/task<br/>Rate: 10/min]
        AgentStatus["GET /api/agent/status/:id"]
        AgentTasks[GET /api/agent/tasks]
        StopAgent["POST /api/agent/stop/:id"]
    end

    subgraph "Notifications"
        NotifyTest[POST /api/notifications/test]
        RequestAttn[POST /api/notifications/request_attention]
        NotifyConfig[GET/POST /api/notifications/config]
        UserActive[POST /api/notifications/user_active<br/>Exempt rate limit]
    end

    subgraph "Email (Auth Required)"
        SendEmail[POST /api/email/send]
        ReadEmail[GET /api/email/read]
        EmailStatus[GET /api/email/status]
    end

    subgraph "Git (Auth Required)"
        GitRepos[GET /api/git/repositories]
        GitStatus[GET /api/git/status]
        GitCommit[POST /api/git/commit]
        GitPush[POST /api/git/push]
    end

    classDef core fill:#e3f2fd,stroke:#1565c0
    classDef embodied fill:#e1f5ff,stroke:#01579b
    classDef io fill:#f3e5f5,stroke:#4a148c
    classDef auth fill:#ffebee,stroke:#c62828

    class Chat,Upload,Status,Logs,History,ClearHist core
    class VirtualWorld,BodyState,WorldState,MoodState,MoodHistory,BehaviorHist,StateHist,GetMem,AddMem,EditMem,DelMem embodied
    class VoiceStart,VoiceStop,Speak,VoiceStatus,Audio,VoiceEvents,VisionStatus,Cameras,SelectCam,StartVision,StopVision,Frame,Entities io
    class SendEmail,ReadEmail,EmailStatus,GitRepos,GitStatus,GitCommit,GitPush auth
```

---

## Mood Evolution System

```mermaid
graph TB
    subgraph "Input Factors"
        TimeSince[Time Since Last Message]
        MsgLength[Message Length]
        IsQuestion[Is Question?]
        InteractionCount[Total Interactions]
        WorldThreats[World Threat Level]
    end

    subgraph "Mood Dimensions"
        Curiosity[Curiosity<br/>0.0 - 1.0]
        Irritation[Irritation<br/>0.0 - 1.0]
        Boredom[Boredom<br/>0.0 - 1.0]
        Attachment[Attachment<br/>0.0 - 1.0]
    end

    subgraph "Derived States"
        Engagement[Engagement<br/>curiosity - boredom]
        Stress[Stress<br/>irritation + boredom/2]
    end

    subgraph "Behavioral Impact"
        ResponseTone[Response Tone<br/>Guidance to LLM]
        Verbosity[Verbosity Level]
        EngagementLevel[Engagement Quality]
        AffectionLevel[Affection Display]
    end

    TimeSince -->|Long gap| Boredom
    TimeSince -->|Very long| Attachment

    MsgLength -->|Very short| Irritation
    MsgLength -->|Spam pattern| Irritation

    IsQuestion -->|Yes| Curiosity

    InteractionCount -->|Increases| Attachment

    WorldThreats -->|High| Irritation

    Curiosity --> Engagement
    Boredom --> Engagement
    Irritation --> Stress
    Boredom --> Stress

    Curiosity -->|High| ResponseTone
    Irritation -->|High| ResponseTone
    Boredom -->|High| ResponseTone
    Attachment -->|High| ResponseTone

    Curiosity --> Verbosity
    Boredom --> Verbosity

    Engagement --> EngagementLevel
    Attachment --> AffectionLevel

    ResponseTone --> LLM[LLM Prompt Enhancement]
    Verbosity --> LLM
    EngagementLevel --> LLM
    AffectionLevel --> LLM

    classDef input fill:#e3f2fd,stroke:#1565c0
    classDef mood fill:#fff3e0,stroke:#ef6c00
    classDef derived fill:#f3e5f5,stroke:#4a148c
    classDef output fill:#e8f5e9,stroke:#2e7d32

    class TimeSince,MsgLength,IsQuestion,InteractionCount,WorldThreats input
    class Curiosity,Irritation,Boredom,Attachment mood
    class Engagement,Stress derived
    class ResponseTone,Verbosity,EngagementLevel,AffectionLevel,LLM output
```

---

## Complete Execution Example: "It's too dark in here"

```mermaid
sequenceDiagram
    actor User
    participant API
    participant Core
    participant World
    participant Cog
    participant Gemini
    participant Behav
    participant Motion
    participant Voice

    User->>API: "It's too dark in here"

    API->>Core: process_message()

    Note over Core: Step 1: World Analysis
    Core->>Core: analyze_message_for_world_cues()
    Core->>World: update_world(environment="dark")

    Note over Core: Step 2: Mood Update
    Core->>World: update_mood(message, is_question=False)
    World->>World: boredom ↓, curiosity ↑

    Note over Core: Step 3: Get Context
    Core->>World: get_current_state()
    World-->>Core: body_state, world_state (dark), mood_state

    Note over Core: Step 4: Cognitive Processing
    Core->>Cog: process_input(message, states)
    Cog->>Cog: Format enhanced prompt<br/>Personality + World (dark) + Body + Mood
    Cog->>Gemini: POST /generateContent

    Note over Gemini: AI Reasoning:<br/>"User needs light,<br/>I should help"

    Gemini-->>Cog: {"goal": "provide_illumination",<br/>"emotion": "helpful",<br/>"confidence": 0.9,<br/>"urgency": 0.5,<br/>"dialogue": "Too dark for you,<br/>sweetheart? Let me light<br/>things up."}

    Cog-->>Core: CognitiveState

    Note over Core: Step 5: Behavior Selection
    Core->>Behav: select_and_execute(cognitive_state)

    Behav->>Behav: IntimidateBehavior.calc_utility() = 0.0
    Behav->>Behav: FriendlyGreetBehavior.calc_utility() = 0.3
    Behav->>Behav: IlluminateBehavior.calc_utility() = 0.9
    Behav->>Behav: RelaxedIdleBehavior.calc_utility() = 0.1

    Note over Behav: IlluminateBehavior wins!

    Behav->>Behav: IlluminateBehavior.execute()
    Behav-->>Core: BodyCommand(posture=RELAXED,<br/>luminance=BRIGHT,<br/>hands=OPEN, duration=3.0)

    Note over Core: Step 6: Motion Translation
    Core->>Motion: apply_body_command()
    Motion->>Motion: BRIGHT → LED 75
    Motion->>Motion: OPEN + RELAXED → hands ~60
    Motion-->>Core: {"led_intensity": 75,<br/>"hands": {"left": 60, "right": 60}}

    Note over Core: Step 7: Update Virtual Body
    Core->>World: update_body(body_command)

    Note over Core: Step 8: Voice Synthesis
    Core->>Voice: synthesize_async("Too dark for you...")
    Voice->>Voice: Queue audio generation
    Voice-->>User: SSE: audio_ready event

    Note over Core: Step 9: Return Response
    Core-->>API: Complete response JSON
    API-->>User: {response, cognitive_state,<br/>body_state, hardware_state,<br/>mood}

    User->>User: UI updates:<br/>- LED glow to 75%<br/>- Hands open<br/>- Play audio<br/>- Display dialogue
```

---

## Technology Stack

```mermaid
graph TB
    subgraph "Frontend"
        HTML[HTML5]
        CSS[CSS3]
        JS[JavaScript]
        Fetch[Fetch API]
        EventSource[EventSource SSE]
    end

    subgraph "Backend Framework"
        Flask[Flask 2.0+]
        FlaskLimiter[Flask-Limiter<br/>Rate Limiting]
        FlaskAuth[Flask-HTTPAuth<br/>Basic Auth]
    end

    subgraph "AI & ML"
        Ollama[Ollama<br/>Local LLM Server]
        GeminiAPI[Google Generative AI<br/>Python SDK]
        OpenRouterAPI[OpenRouter API<br/>HTTP Requests]
        MediaPipe[MediaPipe<br/>Object Detection]
        MistralSTT[Mistral Voxtral<br/>Speech-to-Text]
    end

    subgraph "Computer Vision"
        OpenCV[OpenCV<br/>Camera Capture]
        NumPy[NumPy<br/>Array Processing]
    end

    subgraph "Voice"
        xVAsynth[xVAsynth<br/>TTS Engine]
    end

    subgraph "System"
        Python[Python 3.9+]
        Threading[Threading<br/>Async Operations]
        PSUtil[PSUtil<br/>System Metrics]
        Logging[Logging<br/>Rotating File Handler]
        PyAudio[PyAudio<br/>Microphone Capture]
    end

    subgraph "Data"
        JSON[JSON Files<br/>Persistence]
        DotEnv[python-dotenv<br/>Configuration]
    end

    subgraph "External Services"
        Discord[Discord Webhooks<br/>Notifications]
        Brave[Brave Search API<br/>Web Search]
        SMTP[SMTP/IMAP<br/>Email]
        Git[Git CLI<br/>Version Control]
    end

    Flask --> Python
    FlaskLimiter --> Flask
    FlaskAuth --> Flask

    Ollama --> Python
    GeminiAPI --> Python
    OpenRouterAPI --> Python

    MediaPipe --> OpenCV
    OpenCV --> NumPy

    xVAsynth --> Python
    MistralSTT --> Python

    Threading --> Python
    PSUtil --> Python
    Logging --> Python
    PyAudio --> Python

    JSON --> Python
    DotEnv --> Python

    Discord --> Flask
    Brave --> Flask
    SMTP --> Python
    Git --> Python

    HTML --> Fetch
    Fetch --> Flask
    EventSource --> Flask

    classDef frontend fill:#e3f2fd,stroke:#1565c0
    classDef backend fill:#fff3e0,stroke:#ef6c00
    classDef ai fill:#e1f5ff,stroke:#01579b
    classDef external fill:#f3e5f5,stroke:#4a148c

    class HTML,CSS,JS,Fetch,EventSource frontend
    class Flask,FlaskLimiter,FlaskAuth,Python,Threading,PSUtil,Logging backend
    class Ollama,GeminiAPI,OpenRouterAPI,MediaPipe,OpenCV,NumPy,xVAsynth ai
    class Discord,Brave,SMTP,Git external
```

---

## Security Architecture

```mermaid
graph TB
    subgraph "API Layer Security"
        RateLimit[Rate Limiting<br/>Flask-Limiter<br/>100/min chat<br/>10/min agent]
        Auth[HTTP Basic Auth<br/>Username/Password<br/>for sensitive endpoints]
        CORS[CORS Protection<br/>Origin Validation]
    end

    subgraph "Sandbox Security"
        PathValidation[Path Validation<br/>Prevent Directory Traversal]
        SandboxRoot[Sandbox Root<br/>./sandbox/ only]
        CommandFilter[Command Sandboxing<br/>Workspace Restriction]
    end

    subgraph "Email Security"
        EmailRateLimit[Email Rate Limit<br/>Configurable default 10/hr]
        DomainWhitelist[Domain Whitelist<br/>ALLOWED_EMAIL_DOMAINS]
        EmailToggle[Enable/Disable Toggle<br/>EMAIL_ENABLED flag]
    end

    subgraph "Data Security"
        EnvVars[Environment Variables<br/>.env for secrets]
        NoGitSecrets[.gitignore<br/>.env, API keys]
        SecureStorage[Secure Storage<br/>No hardcoded credentials]
    end

    subgraph "Input Validation"
        JSONValidation[JSON Schema Validation]
        FileTypeCheck[File Type Validation<br/>Image uploads]
        SQLInjectionPrev[No SQL = No SQL Injection]
    end

    subgraph "Protected Endpoints"
        EmailAPI[Email API<br/>Auth Required]
        GitAPI[Git API<br/>Auth Required]
        HardwareAPI[Hardware Override<br/>Public but Rate Limited]
    end

    RateLimit --> EmailAPI
    RateLimit --> GitAPI
    RateLimit --> HardwareAPI

    Auth --> EmailAPI
    Auth --> GitAPI

    PathValidation --> SandboxRoot
    CommandFilter --> SandboxRoot

    EmailRateLimit --> EmailAPI
    DomainWhitelist --> EmailAPI
    EmailToggle --> EmailAPI

    EnvVars --> SecureStorage
    NoGitSecrets --> SecureStorage

    JSONValidation --> EmailAPI
    JSONValidation --> GitAPI
    FileTypeCheck --> HardwareAPI

    classDef security fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef protection fill:#fff3e0,stroke:#e65100

    class RateLimit,Auth,CORS,PathValidation,SandboxRoot,CommandFilter,EmailRateLimit,DomainWhitelist,EmailToggle security
    class EnvVars,NoGitSecrets,SecureStorage,JSONValidation,FileTypeCheck,SQLInjectionPrev protection
```

---

## Future Architecture Expansion

```mermaid
graph TB
    subgraph "Current System"
        Current[Virtual Embodied Agent<br/>Software Only]
    end

    subgraph "Phase 1: Physical Hardware"
        Arduino[Arduino/ESP32<br/>Integration]
        RealLED[Physical LEDs<br/>RGB Control]
        RealServos[Servo Motors<br/>Hand Movement]
        HeadMotor[Head Tracking<br/>Pan/Tilt Motors]
    end

    subgraph "Phase 2: Enhanced Vision"
        FaceRec[Face Recognition<br/>Identity Tracking]
        GestureRec[Gesture Recognition<br/>Hand Signals]
        Spatial3D[3D Spatial Tracking<br/>Depth Sensing]
        SceneUnderstanding[Advanced Scene<br/>Understanding]
    end

    subgraph "Phase 3: Advanced Autonomy"
        MultiAgent[Multi-Agent<br/>Collaboration]
        LongTermProjects[Long-Term<br/>Project Tracking]
        SelfImprovement[Self-Improvement<br/>Learning Loop]
        APIIntegration[External API<br/>Integration]
    end

    subgraph "Phase 4: Personalization"
        UserProfiling[User Profile<br/>Learning]
        RelationshipDynamics[Relationship<br/>Milestones]
        ContextSwitching[Multi-Thread<br/>Conversations]
        ProactiveSuggestions[Proactive Task<br/>Suggestions]
    end

    subgraph "Phase 5: Multimodal"
        AudioInput[Speech-to-Text<br/>Voice Commands]
        ImageGen[Image Generation<br/>Visualizations]
        VideoUnderstanding[Video Processing<br/>Complex Scenarios]
    end

    Current --> Arduino
    Arduino --> RealLED
    Arduino --> RealServos
    Arduino --> HeadMotor

    Current --> FaceRec
    FaceRec --> GestureRec
    GestureRec --> Spatial3D
    Spatial3D --> SceneUnderstanding

    Current --> MultiAgent
    MultiAgent --> LongTermProjects
    LongTermProjects --> SelfImprovement
    SelfImprovement --> APIIntegration

    Current --> UserProfiling
    UserProfiling --> RelationshipDynamics
    RelationshipDynamics --> ContextSwitching
    ContextSwitching --> ProactiveSuggestions

    Current --> AudioInput
    AudioInput --> ImageGen
    ImageGen --> VideoUnderstanding

    classDef current fill:#e8f5e9,stroke:#2e7d32,stroke-width:3px
    classDef phase1 fill:#e3f2fd,stroke:#1565c0
    classDef phase2 fill:#f3e5f5,stroke:#4a148c
    classDef phase3 fill:#fff3e0,stroke:#ef6c00
    classDef phase4 fill:#fce4ec,stroke:#c2185b
    classDef phase5 fill:#e0f2f1,stroke:#00695c

    class Current current
    class Arduino,RealLED,RealServos,HeadMotor phase1
    class FaceRec,GestureRec,Spatial3D,SceneUnderstanding phase2
    class MultiAgent,LongTermProjects,SelfImprovement,APIIntegration phase3
    class UserProfiling,RelationshipDynamics,ContextSwitching,ProactiveSuggestions phase4
    class AudioInput,ImageGen,VideoUnderstanding phase5
```

---

## Design Principles Summary

```mermaid
mindmap
  root((Assaultron<br/>ASR-7<br/>Architecture))
    Separation of Concerns
      Cognitive: Goals & Emotions
      Behavioral: Body Commands
      Motion: Hardware Values
      Never Mix Layers

    Symbolic vs Concrete
      Symbolic Above Motion
        Posture.AGGRESSIVE
        Luminance.INTENSE
        HandState.POINTING
      Concrete in Motion Only
        LED Intensity 0-100
        Hand Position 0-100
        Safety Constraints

    Embodiment
      AI Reasons About Intent
        "I want to illuminate"
        "I feel hostile"
        "I need to protect"
      System Translates to Physical
        Auto Body Expression
        No Stage Directions
        Natural Integration

    Personality Consistency
      Sarcastic/Flirty Tone
      Mood Influences Responses
      Memory About Relationships
      Time-Aware Comments
      Character-First Design

    Emergent Behavior
      Mood Evolves Naturally
      Utility-Based Selection
      AI-Judged Memories
      No Hardcoded Rules
      Organic Interactions

    Real-time Integration
      Continuous Vision Updates
      Mood Evolves Over Time
      Async Voice Synthesis
      Proactive Notifications
      Background Monitoring
```

---

## Quick Reference: Component Interactions

| Component | Inputs | Outputs | Primary Responsibility |
|-----------|--------|---------|----------------------|
| **Cognitive Engine** | User message, world state, body state, mood state, vision data, memories | CognitiveState (goal, emotion, dialogue, memory) | High-level reasoning and response generation |
| **Behavior Arbiter** | CognitiveState, current BodyState | BodyCommand (posture, luminance, hands) | Select appropriate behavior based on utility scores |
| **Motion Controller** | BodyCommand | HardwareState (LED intensity, hand positions) | Translate symbolic states to hardware values |
| **Virtual World** | World updates, body commands, user interactions | BodyState, WorldState, MoodState | Maintain agent's internal state representation |
| **Vision System** | Webcam frames | Detected entities, scene description, threat level | Real-time object detection and scene analysis |
| **Voice System** | Text dialogue | WAV audio files, SSE events | Text-to-speech with Fallout 4 Assaultron voice |
| **Agent Logic** | Task description | Task completion result, file artifacts | Autonomous task execution using ReAct pattern |
| **Notification Manager** | Time, threat level, AI flags | Discord webhook messages | Proactive attention requests and alerts |

---

## Configuration Quick Reference

| Setting | Environment Variable | Default | Purpose |
|---------|---------------------|---------|---------|
| **LLM Provider** | `LLM_PROVIDER` | `gemini` | Choose AI backend: ollama/gemini/openrouter |
| **Gemini API** | `GEMINI_API_KEY` | - | Google Gemini API authentication |
| **Voice Model** | `VOICE_MODEL` | `f4_robot_assaultron` | xVAsynth character voice (TTS output) |
| **Mistral API** | `MISTRAL_KEY` | - | Mistral Voxtral STT authentication |
| **STT Sample Rate** | `STT_SAMPLE_RATE` | `16000` | Audio capture sample rate (Hz) |
| **STT Chunk Duration** | `STT_CHUNK_DURATION_MS` | `480` | Audio chunk size (milliseconds) |
| **Vision Confidence** | - | `0.5` | Object detection threshold (runtime config) |
| **Email Enabled** | `EMAIL_ENABLED` | `false` | Enable/disable email functionality |
| **Git Enabled** | `GIT_ENABLED` | `false` | Enable/disable git operations |
| **Discord Webhook** | `DISCORD_WEBHOOK_URL` | - | Notification delivery endpoint |
| **Sandbox Path** | `SANDBOX_PATH` | `./sandbox` | Agent workspace directory |
| **API Auth** | `API_USERNAME`, `API_PASSWORD` | - | Protected endpoint credentials |

---

*This architecture visualization is auto-generated from the ARCHITECTURE.md documentation. For detailed implementation notes, see the full architecture document.*

**Last Updated**: 2026-02-16
**Architecture Version**: 2.1 (Embodied Agent + Multi-Service Infrastructure + Bidirectional Voice I/O)

**New in v2.1** (2026-02-16):
- Added Speech-to-Text System using Mistral Voxtral API for real-time voice input
- Added STT System Architecture sequence diagram showing microphone → transcription flow
- Updated System Overview to include "Input/Output Systems" with both Voice Output (TTS) and Voice Input (STT)
- Added STT endpoints to "Voice & Speech" API map (9 new endpoints)
- Updated Technology Stack with Mistral Voxtral STT and PyAudio components
- Updated Configuration Quick Reference with MISTRAL_KEY, STT_SAMPLE_RATE, STT_CHUNK_DURATION_MS

**New in v2.0.1** (2026-02-13):
- Added Multi-Service Architecture diagram showing all 4 services orchestrated by run.py
- Added Monitoring System Architecture diagram with metrics collection and dashboard
- Added Discord Bot Integration & Voice Messages sequence diagram
- Updated System Overview to include monitoring dashboard and Discord bot integration
