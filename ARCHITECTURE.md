# Assaultron Embodied Agent Architecture

## Overview
This document describes the refactored behavior-based architecture that transforms the Assaultron from a tool-using chatbot into a fully embodied agent operating within a virtual environment.

---

## Design Principles

1. **Separation of Concerns**: Cognition, behavior, and actuation are cleanly separated
2. **Intent-Based Control**: The LLM reasons about goals and emotions, NOT hardware
3. **Deterministic Execution**: Behaviors are predictable, debuggable, and safe
4. **Future-Proof**: Compatible with real robotics hardware
5. **Personality Preservation**: Maintains ASR-7's unique character

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INPUT                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                 COGNITIVE LAYER                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  LLM (Ollama) + Personality (ASR-7)                  │   │
│  │  - Dialogue generation                               │   │
│  │  - Intent reasoning                                  │   │
│  │  - Emotional state modeling                          │   │
│  │  - Attention/focus selection                         │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                      │
│               ┌───────▼────────┐                            │
│               │  CognitiveState │                            │
│               │  - goal         │                            │
│               │  - emotion      │                            │
│               │  - urgency      │                            │
│               │  - confidence   │                            │
│               │  - focus        │                            │
│               │  - dialogue     │                            │
│               └───────┬─────────┘                            │
└───────────────────────┼──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                 BEHAVIORAL LAYER                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Behavior Arbiter (Utility-Based Selection)          │   │
│  │  - Receives CognitiveState                           │   │
│  │  - Evaluates behavior utilities                      │   │
│  │  - Selects appropriate behavior                      │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                      │
│       ┌───────────────┴───────────────┐                     │
│       │     Behavior Library          │                     │
│       │  - IntimidateBehavior         │                     │
│       │  - FriendlyGreetBehavior      │                     │
│       │  - AlertScanBehavior          │                     │
│       │  - RelaxedIdleBehavior        │                     │
│       │  - CuriousExploreBehavior     │                     │
│       │  - ProtectiveBehavior         │                     │
│       │  - PlayfulBehavior            │                     │
│       └───────────────┬───────────────┘                     │
│                       │                                      │
│               ┌───────▼────────┐                            │
│               │  Behavior       │                            │
│               │  - posture      │                            │
│               │  - gesture      │                            │
│               │  - luminance    │                            │
│               │  - attention    │                            │
│               │  - duration     │                            │
│               └───────┬─────────┘                            │
└───────────────────────┼──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│              VIRTUAL BODY / WORLD MODEL                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Body State                                           │   │
│  │  - posture: (idle|alert|aggressive|relaxed|curious)  │   │
│  │  - luminance: (dim|soft|normal|bright|intense)       │   │
│  │  - left_hand: (closed|open|pointing|relaxed)         │   │
│  │  - right_hand: (closed|open|pointing|relaxed)        │   │
│  │  - head_orientation: Vector3 (future)                │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  World State                                          │   │
│  │  - entities: [detected_entity_id, ...]               │   │
│  │  - environment: (dark|normal|bright)                 │   │
│  │  - threat_level: (none|low|medium|high)              │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────┼──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│             MOTION / ACTUATOR LAYER                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Motion Controller                                    │   │
│  │  - Translates high-level body states to hardware     │   │
│  │  - Smooth interpolation                              │   │
│  │  - Safety constraints                                │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                      │
│       ┌───────────────┴───────────────┐                     │
│       │   Hardware Mappings           │                     │
│       │  posture → hand positions     │                     │
│       │  luminance → LED intensity    │                     │
│       │  attention → head direction   │                     │
│       └───────────────┬───────────────┘                     │
│                       │                                      │
│               ┌───────▼────────┐                            │
│               │  Hardware State │                            │
│               │  - led_intensity│                            │
│               │  - hand_left    │                            │
│               │  - hand_right   │                            │
│               └───────┬─────────┘                            │
└───────────────────────┼──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│               HARDWARE SERVER (unchanged)                    │
│               Polls state → Arduino/ESP32                    │
└──────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Cognitive Layer

### Responsibility
- Natural language understanding and generation
- High-level reasoning about goals and intentions
- Emotional state modeling
- Dialogue management

### Input
- User message (text)
- Memory context
- World state

### Output: CognitiveState
```python
@dataclass
class CognitiveState:
    goal: str              # e.g., "intimidate_intruder", "greet_friend", "idle"
    emotion: str           # e.g., "hostile", "friendly", "curious", "neutral"
    confidence: float      # 0.0 - 1.0
    urgency: float         # 0.0 - 1.0 (how quickly to act)
    focus: Optional[str]   # target entity ID or None
    dialogue: str          # natural language response to user
```

### LLM Prompt Structure
The LLM prompt is redesigned to:
1. Define ASR-7's identity and personality (unchanged)
2. Describe the virtual body and available states
3. Request structured output (goal + emotion + confidence + urgency + focus)
4. Remove all references to tools, LEDs, motors, angles, etc.

Example LLM output:
```json
{
    "goal": "intimidate_intruder",
    "emotion": "hostile",
    "confidence": 0.85,
    "urgency": 0.7,
    "focus": "human_entity_1",
    "dialogue": "You picked the wrong storage room to snoop around in, pal."
}
```

---

## Layer 2: Behavioral Layer

### Responsibility
- Select appropriate behavior based on CognitiveState
- Execute behavior to produce body commands
- Manage behavior transitions

### Behavior Arbiter
Uses **utility-based selection**:
- Each behavior calculates a utility score based on:
  - Goal match
  - Emotion compatibility
  - Urgency
  - Current body state
- Highest utility wins

### Behavior Base Class
```python
class Behavior(ABC):
    @abstractmethod
    def calculate_utility(self, cognitive_state: CognitiveState,
                          body_state: BodyState) -> float:
        pass

    @abstractmethod
    def execute(self, cognitive_state: CognitiveState,
                body_state: BodyState) -> BodyCommand:
        pass
```

### Predefined Behaviors

| Behavior | Goal Triggers | Emotion | Posture | Luminance | Hands |
|----------|--------------|---------|---------|-----------|-------|
| **IntimidateBehavior** | intimidate, threaten | hostile, angry | aggressive | intense | closed (fists) |
| **FriendlyGreetBehavior** | greet, welcome | friendly, happy | relaxed | soft | open |
| **AlertScanBehavior** | scan, investigate | suspicious, cautious | alert | bright | pointing |
| **RelaxedIdleBehavior** | idle, wait | neutral, content | idle | dim | relaxed |
| **CuriousExploreBehavior** | explore, investigate | curious | curious | normal | pointing |
| **ProtectiveBehavior** | protect, guard | protective, alert | alert | bright | closed |
| **PlayfulBehavior** | tease, joke | playful, mischievous | relaxed | soft | open |

### Output: BodyCommand
```python
@dataclass
class BodyCommand:
    posture: str           # idle, alert, aggressive, relaxed, curious
    luminance: str         # dim, soft, normal, bright, intense
    left_hand: str         # closed, open, pointing, relaxed
    right_hand: str        # closed, open, pointing, relaxed
    attention_target: Optional[str]  # entity to "look at"
    duration: float        # how long to hold this pose (seconds)
```

---

## Layer 3: Virtual Body / World Model

### BodyState (Current State)
```python
@dataclass
class BodyState:
    posture: str = "idle"
    luminance: str = "dim"
    left_hand: str = "relaxed"
    right_hand: str = "relaxed"
    head_orientation: tuple = (0, 0, 0)  # Future: (pitch, yaw, roll)
    last_updated: datetime = field(default_factory=datetime.now)
```

### WorldState (Environment Perception)
```python
@dataclass
class WorldState:
    entities: List[str] = field(default_factory=list)  # Detected entities
    environment: str = "normal"  # dark, normal, bright
    threat_level: str = "none"   # none, low, medium, high
    time_of_day: str = "unknown" # Future: integrate time context
```

### Virtual Body Semantics
The virtual body defines **symbolic states** that are hardware-agnostic:
- **Postures**: idle, alert, aggressive, relaxed, curious
- **Luminance**: dim, soft, normal, bright, intense
- **Hand States**: closed, open, pointing, relaxed
- **Attention**: where the agent is "looking" (symbolic)

These states have **meaning** in the agent's cognitive model and will be translated to hardware by the Motion Layer.

---

## Layer 4: Motion / Actuator Layer

### Responsibility
- Translate abstract body states to concrete hardware commands
- Apply smooth interpolation (future)
- Enforce safety constraints
- Maintain hardware state synchronization

### Motion Controller
Maps symbolic states to hardware values:

```python
# Posture → Hand Positions
POSTURE_MAPPINGS = {
    "idle": {"left": 0, "right": 0},         # Hands relaxed/closed
    "alert": {"left": 30, "right": 30},      # Slightly open, ready
    "aggressive": {"left": 0, "right": 0},   # Fists clenched
    "relaxed": {"left": 50, "right": 50},    # Hands open, calm
    "curious": {"left": 70, "right": 70}     # Hands extended, exploring
}

# Luminance → LED Intensity
LUMINANCE_MAPPINGS = {
    "dim": 10,
    "soft": 35,
    "normal": 50,
    "bright": 75,
    "intense": 100
}

# Hand State → Position Modifier
HAND_STATE_MAPPINGS = {
    "closed": 0,
    "relaxed": 30,
    "open": 70,
    "pointing": 50
}
```

### Safety Constraints
- LED intensity clamped: 0-100
- Hand positions clamped: 0-100
- Rate limiting: max state changes per second
- Smooth transitions: interpolate between states (future)

### Output
Updates `hardware_state` dict (existing format) for compatibility with `hardware_server.py`:
```python
hardware_state = {
    "led_intensity": 75,
    "hands": {
        "left": {"position": 30, "status": "open"},
        "right": {"position": 30, "status": "open"}
    }
}
```

---

## Data Flow Example

### User Input: "It's too dark in here."

**1. Cognitive Layer**
- LLM receives: user message + memory + world state
- LLM outputs:
```json
{
    "goal": "provide_illumination",
    "emotion": "helpful",
    "confidence": 0.9,
    "urgency": 0.5,
    "focus": null,
    "dialogue": "Too dark for you, sweetheart? Let me light things up."
}
```

**2. Behavioral Layer**
- Behavior Arbiter evaluates all behaviors
- **FriendlyGreetBehavior** scores highest utility (helpful emotion + no threat)
- Behavior executes:
```python
BodyCommand(
    posture="relaxed",
    luminance="bright",
    left_hand="open",
    right_hand="open",
    attention_target=None,
    duration=3.0
)
```

**3. Virtual Body**
- Updates BodyState:
```python
body_state.posture = "relaxed"
body_state.luminance = "bright"
body_state.left_hand = "open"
body_state.right_hand = "open"
```

**4. Motion Controller**
- Translates to hardware:
```python
hardware_state["led_intensity"] = 75  # "bright"
hardware_state["hands"]["left"]["position"] = 70  # "open"
hardware_state["hands"]["right"]["position"] = 70  # "open"
```

**5. Hardware Server**
- Polls hardware_state
- Sends to Arduino
- LED brightens, hands open

**6. User sees:**
- Dialogue: "Too dark for you, sweetheart? Let me light things up."
- Hardware: LED brightness increases, hands open in friendly gesture

---

## Implementation Strategy

### Phase 1: Core Architecture
1. Create new modules:
   - `cognitive_layer.py` - LLM interface + CognitiveState
   - `behavioral_layer.py` - Behavior arbiter + behavior library
   - `virtual_body.py` - BodyState, WorldState, BodyCommand
   - `motion_controller.py` - Hardware translation + mappings

2. Update `config.py`:
   - New LLM prompt (intent-based)
   - Define goal/emotion vocabularies
   - Define behavior configurations

3. Refactor `main.py`:
   - Replace tool system with layered pipeline
   - Integrate cognitive → behavioral → motion flow
   - Preserve existing Flask API

### Phase 2: Behavior Library
1. Implement 7 core behaviors
2. Define utility functions for each
3. Test behavior selection logic

### Phase 3: Integration
1. Connect layers in main.py
2. Test end-to-end flow
3. Validate hardware compatibility

### Phase 4: Enhancement (Future)
1. Add behavior trees for complex sequences
2. Implement smooth motion interpolation
3. Add head/camera orientation control
4. Integrate computer vision for entity detection
5. Add behavior learning/adaptation

---

## Migration Notes

### What Changes
- **Tool system removed**: No more `[TOOL:...]` tags
- **Direct hardware references removed**: LLM never mentions LEDs/motors
- **New output format**: CognitiveState JSON instead of natural language with tool tags

### What Stays
- **Personality**: ASR-7 character and dialogue style unchanged
- **Voice system**: TTS integration unchanged
- **Hardware server**: Polling mechanism unchanged
- **REST API**: Endpoints preserved (internal logic changes)
- **Web UI**: Frontend works as-is

### Backward Compatibility
The system maintains the same external interface:
- `/api/chat` still accepts text, returns response + hardware state
- `/api/hardware` still returns LED/hand state
- Hardware server still polls the same state format

---

## Benefits of New Architecture

1. **Scalability**: Easy to add new behaviors without modifying LLM prompt
2. **Debuggability**: Each layer can be tested independently
3. **Safety**: Behaviors are predictable, no arbitrary hardware commands
4. **Realism**: Agent "thinks" about goals/emotions, not motor angles
5. **Future-proof**: Ready for real robotics (CV, SLAM, manipulation)
6. **Maintainability**: Clear separation of concerns

---

## Testing Strategy

### Unit Tests
- Cognitive Layer: Mock LLM outputs, verify CognitiveState parsing
- Behavioral Layer: Test utility calculations, behavior selection
- Motion Controller: Verify state mappings, safety constraints

### Integration Tests
- Full pipeline: User input → hardware state
- Behavior transitions: Verify smooth state changes
- Edge cases: Invalid inputs, conflicting goals

### Validation
- Compare old vs new system outputs for same inputs
- Verify personality preservation
- Test hardware synchronization

---

## Future Enhancements

### Short-term
- Add more behaviors (investigative, fearful, affectionate)
- Implement behavior blending (smooth transitions)
- Add behavior cooldowns (prevent rapid switching)

### Medium-term
- Integrate computer vision (entity detection)
- Add spatial awareness (room mapping)
- Implement memory-influenced behaviors

### Long-term
- Full behavior tree system
- Learning from interactions
- Multi-agent coordination (if multiple robots)
- Real-world hardware integration (motors, sensors, cameras)

---

## Conclusion

This architecture transforms the Assaultron from a chatbot with hardware control tools into a true embodied agent that reasons about its goals and emotions, then expresses them through a virtual body. The system is modular, testable, and ready for future expansion into real-world robotics while preserving the unique ASR-7 personality.
