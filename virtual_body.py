"""
Virtual Body and World Model for Assaultron Embodied Agent

This module defines the virtual environment in which the AI exists.
It provides symbolic representations of body state and world perception,
completely decoupled from hardware primitives.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================================
# ENUMERATIONS - Symbolic States
# ============================================================================

class Posture(str, Enum):
    """High-level body postures representing the agent's physical demeanor"""
    IDLE = "idle"              # Neutral, at rest
    ALERT = "alert"            # Attentive, ready to respond
    AGGRESSIVE = "aggressive"  # Threatening, confrontational
    RELAXED = "relaxed"        # Calm, open, friendly
    CURIOUS = "curious"        # Investigating, exploring


class Luminance(str, Enum):
    """Symbolic representation of the agent's luminous intensity"""
    DIM = "dim"            # Minimal light (resting, low-key)
    SOFT = "soft"          # Gentle glow (friendly, calm)
    NORMAL = "normal"      # Standard operational brightness
    BRIGHT = "bright"      # High visibility (alert, active)
    INTENSE = "intense"    # Maximum intensity (threatening, urgent)


class HandState(str, Enum):
    """Symbolic hand configurations"""
    CLOSED = "closed"      # Fist, tense
    RELAXED = "relaxed"    # Partially open, neutral
    OPEN = "open"          # Fully open, welcoming
    POINTING = "pointing"  # Directed, indicating


class Environment(str, Enum):
    """Perceived environmental lighting conditions"""
    DARK = "dark"
    NORMAL = "normal"
    BRIGHT = "bright"


class ThreatLevel(str, Enum):
    """Perceived threat level in the environment"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class BodyState:
    """
    Current state of the virtual body.

    This represents the agent's physical configuration at any moment.
    All states are symbolic - they describe WHAT the body is doing,
    not HOW the hardware achieves it.
    """
    posture: Posture = Posture.IDLE
    luminance: Luminance = Luminance.DIM
    left_hand: HandState = HandState.RELAXED
    right_hand: HandState = HandState.RELAXED

    # Future expansion: spatial orientation
    head_orientation: tuple = (0.0, 0.0, 0.0)  # (pitch, yaw, roll) in degrees

    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "posture": self.posture.value,
            "luminance": self.luminance.value,
            "left_hand": self.left_hand.value,
            "right_hand": self.right_hand.value,
            "head_orientation": self.head_orientation,
            "last_updated": self.last_updated.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BodyState':
        """Deserialize from dictionary"""
        return cls(
            posture=Posture(data.get("posture", "idle")),
            luminance=Luminance(data.get("luminance", "dim")),
            left_hand=HandState(data.get("left_hand", "relaxed")),
            right_hand=HandState(data.get("right_hand", "relaxed")),
            head_orientation=tuple(data.get("head_orientation", (0.0, 0.0, 0.0))),
            last_updated=datetime.fromisoformat(data["last_updated"]) if "last_updated" in data else datetime.now()
        )


@dataclass
class WorldState:
    """
    Perceived state of the world around the agent.

    This represents the agent's understanding of its environment,
    including detected entities, environmental conditions, and threats.
    """
    # Detected entities (future: CV integration will populate this)
    entities: List[str] = field(default_factory=list)

    # Environmental perception
    environment: Environment = Environment.NORMAL
    threat_level: ThreatLevel = ThreatLevel.NONE

    # Temporal context
    time_of_day: str = "unknown"  # Future: "morning", "afternoon", "evening", "night"

    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "entities": self.entities,
            "environment": self.environment.value,
            "threat_level": self.threat_level.value,
            "time_of_day": self.time_of_day,
            "last_updated": self.last_updated.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorldState':
        """Deserialize from dictionary"""
        return cls(
            entities=data.get("entities", []),
            environment=Environment(data.get("environment", "normal")),
            threat_level=ThreatLevel(data.get("threat_level", "none")),
            time_of_day=data.get("time_of_day", "unknown"),
            last_updated=datetime.fromisoformat(data["last_updated"]) if "last_updated" in data else datetime.now()
        )


@dataclass
class BodyCommand:
    """
    Command to transition the body to a new state.

    Emitted by behaviors and executed by the motion controller.
    Represents a desired body configuration, not hardware commands.
    """
    posture: Posture
    luminance: Luminance
    left_hand: HandState
    right_hand: HandState

    # Optional attention target (entity ID to "look at")
    attention_target: Optional[str] = None

    # Duration to hold this configuration (seconds)
    # 0.0 = instantaneous, >0 = hold for specified time
    duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "posture": self.posture.value,
            "luminance": self.luminance.value,
            "left_hand": self.left_hand.value,
            "right_hand": self.right_hand.value,
            "attention_target": self.attention_target,
            "duration": self.duration
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BodyCommand':
        """Deserialize from dictionary"""
        return cls(
            posture=Posture(data["posture"]),
            luminance=Luminance(data["luminance"]),
            left_hand=HandState(data["left_hand"]),
            right_hand=HandState(data["right_hand"]),
            attention_target=data.get("attention_target"),
            duration=data.get("duration", 0.0)
        )


@dataclass
class MoodState:
    """
    Internal mood/emotional state that evolves over time.

    This is INTERNAL ONLY - displayed in UI but cannot be directly controlled.
    Mood subtly affects behavior tone, verbosity, and responsiveness.
    """
    # Core mood dimensions (0.0 - 1.0)
    curiosity: float = 0.5          # Interest in surroundings and questions
    irritation: float = 0.0         # Frustration or annoyance
    boredom: float = 0.0            # Lack of stimulation
    attachment: float = 0.3         # Emotional bond to operator

    # Derived states
    engagement: float = 0.5         # How interested/present the agent is
    stress: float = 0.0             # Anxiety or tension level

    # Temporal tracking
    last_interaction: datetime = field(default_factory=datetime.now)
    interaction_count: int = 0

    def __post_init__(self):
        """Validate all ranges"""
        self.curiosity = max(0.0, min(1.0, self.curiosity))
        self.irritation = max(0.0, min(1.0, self.irritation))
        self.boredom = max(0.0, min(1.0, self.boredom))
        self.attachment = max(0.0, min(1.0, self.attachment))
        self.engagement = max(0.0, min(1.0, self.engagement))
        self.stress = max(0.0, min(1.0, self.stress))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "curiosity": round(self.curiosity, 2),
            "irritation": round(self.irritation, 2),
            "boredom": round(self.boredom, 2),
            "attachment": round(self.attachment, 2),
            "engagement": round(self.engagement, 2),
            "stress": round(self.stress, 2),
            "last_interaction": self.last_interaction.isoformat(),
            "interaction_count": self.interaction_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MoodState':
        """Deserialize from dictionary"""
        return cls(
            curiosity=data.get("curiosity", 0.5),
            irritation=data.get("irritation", 0.0),
            boredom=data.get("boredom", 0.0),
            attachment=data.get("attachment", 0.3),
            engagement=data.get("engagement", 0.5),
            stress=data.get("stress", 0.0),
            last_interaction=datetime.fromisoformat(data["last_interaction"]) if "last_interaction" in data else datetime.now(),
            interaction_count=data.get("interaction_count", 0)
        )


@dataclass
class CognitiveState:
    """
    Output from the cognitive layer (LLM).

    This represents the agent's high-level intentions and emotional state,
    NOT physical actions. The behavioral layer interprets this to select behaviors.
    """
    # Primary goal (what the agent wants to achieve)
    goal: str  # e.g., "intimidate_intruder", "greet_friend", "idle", "provide_illumination"

    # Emotional state
    emotion: str  # e.g., "hostile", "friendly", "curious", "neutral", "playful"

    # Confidence in the current assessment (0.0 - 1.0)
    confidence: float

    # Urgency of action (0.0 - 1.0)
    # 0.0 = no rush, 1.0 = immediate action required
    urgency: float

    # Focus target (entity ID or None)
    focus: Optional[str] = None

    # Natural language dialogue response
    dialogue: str = ""

    # Potential long-term memory to store (if important)
    memory: Optional[str] = None

    # Attention request flags
    needs_attention: bool = False  # Whether AI wants user's attention
    attention_reason: Optional[str] = None  # Why attention is needed

    # Debug: raw LLM response before parsing/sanitization
    raw_response: Optional[str] = None

    def __post_init__(self):
        """Validate ranges"""
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.urgency = max(0.0, min(1.0, self.urgency))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "goal": self.goal,
            "emotion": self.emotion,
            "confidence": self.confidence,
            "urgency": self.urgency,
            "focus": self.focus,
            "dialogue": self.dialogue,
            "memory": self.memory,
            "needs_attention": self.needs_attention,
            "attention_reason": self.attention_reason,
            "raw_response": self.raw_response
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CognitiveState':
        """Deserialize from dictionary"""
        return cls(
            goal=data["goal"],
            emotion=data["emotion"],
            confidence=data["confidence"],
            urgency=data["urgency"],
            focus=data.get("focus"),
            dialogue=data.get("dialogue", ""),
            memory=data.get("memory"),
            needs_attention=data.get("needs_attention", False),
            attention_reason=data.get("attention_reason")
        )


# ============================================================================
# VIRTUAL WORLD MANAGER
# ============================================================================

class VirtualWorld:
    """
    Manages the virtual environment state.

    This is the "simulation" the agent exists within. It tracks:
    - The agent's body state
    - The world state (environment, entities)
    - Internal mood state (read-only, emergent)
    - State history (for debugging)
    """

    def __init__(self):
        self.body_state = BodyState()
        self.world_state = WorldState()
        self.mood_state = self._load_mood_state()
        self.state_history: List[Dict[str, Any]] = []
        self.mood_history: List[Dict[str, Any]] = []
        self.max_history = 100
        self.mood_file = "mood_state.json"

    def update_body(self, command: BodyCommand) -> None:
        """
        Apply a body command to update the virtual body state.

        Args:
            command: Desired body configuration
        """
        old_state = self.body_state.to_dict()

        self.body_state.posture = command.posture
        self.body_state.luminance = command.luminance
        self.body_state.left_hand = command.left_hand
        self.body_state.right_hand = command.right_hand
        self.body_state.last_updated = datetime.now()

        # Log state transition
        self._log_transition(old_state, self.body_state.to_dict(), command)

    def update_world(self, **kwargs) -> None:
        """
        Update world state perception.

        Args:
            **kwargs: Fields to update (entities, environment, threat_level, etc.)
        """
        if "entities" in kwargs:
            self.world_state.entities = kwargs["entities"]
        if "environment" in kwargs:
            self.world_state.environment = Environment(kwargs["environment"])
        if "threat_level" in kwargs:
            self.world_state.threat_level = ThreatLevel(kwargs["threat_level"])
        if "time_of_day" in kwargs:
            self.world_state.time_of_day = kwargs["time_of_day"]

        self.world_state.last_updated = datetime.now()

    def get_body_state(self) -> BodyState:
        """Get current body state"""
        return self.body_state

    def get_world_state(self) -> WorldState:
        """Get current world state"""
        return self.world_state

    def get_mood_state(self) -> MoodState:
        """Get current internal mood state"""
        return self.mood_state

    def update_mood(self,
                    user_message: str = "",
                    is_question: bool = False,
                    message_length: int = 0) -> None:
        """
        Update internal mood based on interaction patterns.

        Mood evolves based on:
        - Time since last interaction (boredom increases)
        - Interaction frequency (attachment changes)
        - Question asking (curiosity increases)
        - Repeated short messages (irritation increases)
        """
        now = datetime.now()
        time_since_last = (now - self.mood_state.last_interaction).total_seconds()

        # Boredom increases over time without interaction
        if time_since_last > 300:  # 5 minutes
            self.mood_state.boredom = min(1.0, self.mood_state.boredom + 0.1)
        elif time_since_last > 600:  # 10 minutes
            self.mood_state.boredom = min(1.0, self.mood_state.boredom + 0.2)

        # New interaction - reset boredom, increase engagement
        if user_message:
            self.mood_state.boredom = max(0.0, self.mood_state.boredom - 0.15)
            self.mood_state.engagement = min(1.0, self.mood_state.engagement + 0.1)
            self.mood_state.interaction_count += 1
            self.mood_state.last_interaction = now

            # Questions increase curiosity
            if is_question:
                self.mood_state.curiosity = min(1.0, self.mood_state.curiosity + 0.05)

            # Very short messages can be irritating if repeated
            if message_length < 10 and self.mood_state.interaction_count % 5 == 0:
                self.mood_state.irritation = min(1.0, self.mood_state.irritation + 0.03)

            # Longer meaningful interactions reduce irritation
            if message_length > 50:
                self.mood_state.irritation = max(0.0, self.mood_state.irritation - 0.05)

            # Attachment grows slowly with interactions
            if self.mood_state.interaction_count % 10 == 0:
                self.mood_state.attachment = min(1.0, self.mood_state.attachment + 0.02)

        # Calculate derived states
        self.mood_state.engagement = max(0.0, min(1.0,
            (self.mood_state.curiosity * 0.5) +
            ((1.0 - self.mood_state.boredom) * 0.5)
        ))

        self.mood_state.stress = max(0.0, min(1.0,
            (self.mood_state.irritation * 0.7) +
            (self.mood_state.boredom * 0.3)
        ))

        # Natural decay over time
        self.mood_state.curiosity = max(0.3, self.mood_state.curiosity - 0.01)
        self.mood_state.irritation = max(0.0, self.mood_state.irritation - 0.02)

        # Log mood changes
        self._log_mood_transition()

        # Save mood state to disk
        self._save_mood_state()

    def _log_mood_transition(self) -> None:
        """Log mood state changes for history tracking"""
        mood_entry = {
            "timestamp": datetime.now().isoformat(),
            "mood": self.mood_state.to_dict()
        }

        self.mood_history.append(mood_entry)

        # Limit mood history size
        if len(self.mood_history) > self.max_history:
            self.mood_history.pop(0)

    def get_mood_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent mood history"""
        return self.mood_history[-limit:]

    def _log_transition(self, old_state: Dict, new_state: Dict, command: BodyCommand) -> None:
        """Log state transitions for debugging"""
        transition = {
            "timestamp": datetime.now().isoformat(),
            "old_state": old_state,
            "new_state": new_state,
            "command": command.to_dict()
        }

        self.state_history.append(transition)

        # Limit history size
        if len(self.state_history) > self.max_history:
            self.state_history.pop(0)

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent state transition history"""
        return self.state_history[-limit:]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize entire world state"""
        return {
            "body_state": self.body_state.to_dict(),
            "world_state": self.world_state.to_dict(),
            "mood_state": self.mood_state.to_dict(),
            "history_size": len(self.state_history),
            "mood_history_size": len(self.mood_history)
        }

    def _save_mood_state(self) -> None:
        """Save mood state to disk"""
        try:
            import json
            with open(self.mood_file, 'w', encoding='utf-8') as f:
                json.dump(self.mood_state.to_dict(), f, indent=2)
        except Exception as e:
            print(f"[MOOD ERROR] Failed to save mood state: {e}")

    def _load_mood_state(self) -> MoodState:
        """Load mood state from disk"""
        try:
            import os
            import json
            if os.path.exists("mood_state.json"):
                with open("mood_state.json", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return MoodState.from_dict(data)
        except Exception as e:
            print(f"[MOOD ERROR] Failed to load mood state: {e}")
        return MoodState()

    def set_mood_manually(self, **kwargs) -> None:
        """
        Manually set mood parameters (for UI control).

        Accepts: curiosity, irritation, boredom, attachment
        """
        if "curiosity" in kwargs:
            self.mood_state.curiosity = max(0.0, min(1.0, float(kwargs["curiosity"])))
        if "irritation" in kwargs:
            self.mood_state.irritation = max(0.0, min(1.0, float(kwargs["irritation"])))
        if "boredom" in kwargs:
            self.mood_state.boredom = max(0.0, min(1.0, float(kwargs["boredom"])))
        if "attachment" in kwargs:
            self.mood_state.attachment = max(0.0, min(1.0, float(kwargs["attachment"])))

        # Recalculate derived states
        self.mood_state.engagement = max(0.0, min(1.0,
            (self.mood_state.curiosity * 0.5) +
            ((1.0 - self.mood_state.boredom) * 0.5)
        ))

        self.mood_state.stress = max(0.0, min(1.0,
            (self.mood_state.irritation * 0.7) +
            (self.mood_state.boredom * 0.3)
        ))

        # Save to disk
        self._save_mood_state()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def analyze_user_message_for_world_cues(message: str) -> Dict[str, Any]:
    """
    Analyze user message for environmental cues that should update world state.

    This is a simple heuristic parser. In the future, this could be replaced
    with more sophisticated NLP or even CV-based perception.

    Args:
        message: User's text input

    Returns:
        Dictionary of world state updates
    """
    message_lower = message.lower()
    updates = {}

    # Detect lighting conditions
    if any(word in message_lower for word in ["dark", "dim", "can't see"]):
        updates["environment"] = "dark"
    elif any(word in message_lower for word in ["bright", "too much light", "blinding"]):
        updates["environment"] = "bright"

    # Detect threat cues
    if any(word in message_lower for word in ["intruder", "threat", "danger", "help", "attack"]):
        updates["threat_level"] = "high"
    elif any(word in message_lower for word in ["suspicious", "watch out", "careful"]):
        updates["threat_level"] = "medium"
    elif any(word in message_lower for word in ["safe", "all clear", "relax"]):
        updates["threat_level"] = "none"

    # Future: time of day, entity detection, etc.

    return updates


# ============================================================================
# EXAMPLE USAGE (for testing)
# ============================================================================

if __name__ == "__main__":
    # Create virtual world
    world = VirtualWorld()

    print("Initial State:")
    print(f"  Body: {world.body_state.to_dict()}")
    print(f"  World: {world.world_state.to_dict()}")

    # Update world based on user input
    updates = analyze_user_message_for_world_cues("It's too dark in here!")
    world.update_world(**updates)
    print(f"\nWorld updated: {updates}")

    # Create and apply a body command
    command = BodyCommand(
        posture=Posture.RELAXED,
        luminance=Luminance.BRIGHT,
        left_hand=HandState.OPEN,
        right_hand=HandState.OPEN,
        duration=3.0
    )

    world.update_body(command)
    print(f"\nBody updated:")
    print(f"  {world.body_state.to_dict()}")

    # Check history
    print(f"\nTransition history: {len(world.get_history())} entries")
