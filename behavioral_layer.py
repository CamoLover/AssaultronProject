"""
Behavioral Layer - Behavior Selection and Execution

This module implements the behavioral architecture that translates
high-level cognitive states into concrete body commands.

Uses utility-based behavior selection: each behavior calculates a
utility score based on the current cognitive state, and the highest
scoring behavior is selected and executed.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from virtual_body import (
    CognitiveState, BodyState, BodyCommand,
    Posture, Luminance, HandState
)


# ============================================================================
# BEHAVIOR BASE CLASS
# ============================================================================

class Behavior(ABC):
    """
    Abstract base class for all behaviors.

    Each behavior:
    1. Calculates utility based on cognitive state
    2. Executes to produce a body command
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def calculate_utility(self, cognitive_state: CognitiveState, body_state: BodyState) -> float:
        """
        Calculate utility score for this behavior.

        Args:
            cognitive_state: Current cognitive state from LLM
            body_state: Current body configuration

        Returns:
            Utility score (0.0 - 1.0+)
            Higher scores = more appropriate behavior
        """
        pass

    @abstractmethod
    def execute(self, cognitive_state: CognitiveState, body_state: BodyState) -> BodyCommand:
        """
        Execute the behavior to produce a body command.

        Args:
            cognitive_state: Current cognitive state
            body_state: Current body configuration

        Returns:
            BodyCommand to apply to the virtual body
        """
        pass

    def __repr__(self) -> str:
        return f"<Behavior: {self.name}>"


# ============================================================================
# BEHAVIOR LIBRARY
# ============================================================================

class IntimidateBehavior(Behavior):
    """
    Threatening, aggressive posture.
    Triggered by hostile emotions and intimidation goals.
    """

    def __init__(self):
        super().__init__("Intimidate")

    def calculate_utility(self, cognitive_state: CognitiveState, body_state: BodyState) -> float:
        utility = 0.0

        # Strong match for intimidation goal
        if cognitive_state.goal in ["intimidate", "threaten", "protect"]:
            utility += 0.6

        # Match hostile/protective emotions
        if cognitive_state.emotion in ["hostile", "angry", "protective"]:
            utility += 0.3

        # Urgency boosts this behavior
        utility += cognitive_state.urgency * 0.2

        return utility * cognitive_state.confidence

    def execute(self, cognitive_state: CognitiveState, body_state: BodyState) -> BodyCommand:
        return BodyCommand(
            posture=Posture.AGGRESSIVE,
            luminance=Luminance.INTENSE,
            left_hand=HandState.CLOSED,  # Fists clenched
            right_hand=HandState.CLOSED,
            attention_target=cognitive_state.focus,
            duration=2.0
        )


class FriendlyGreetBehavior(Behavior):
    """
    Warm, welcoming posture.
    Triggered by friendly emotions and greeting goals.
    """

    def __init__(self):
        super().__init__("FriendlyGreet")

    def calculate_utility(self, cognitive_state: CognitiveState, body_state: BodyState) -> float:
        utility = 0.0

        # Match greeting/assist goals
        if cognitive_state.goal in ["greet", "assist", "express_affection"]:
            utility += 0.6

        # Match friendly emotions
        if cognitive_state.emotion in ["friendly", "affectionate", "playful"]:
            utility += 0.3

        # Low urgency is fine for greetings
        utility += 0.1

        return utility * cognitive_state.confidence

    def execute(self, cognitive_state: CognitiveState, body_state: BodyState) -> BodyCommand:
        return BodyCommand(
            posture=Posture.RELAXED,
            luminance=Luminance.SOFT,
            left_hand=HandState.OPEN,  # Welcoming gesture
            right_hand=HandState.OPEN,
            attention_target=cognitive_state.focus,
            duration=2.0
        )


class AlertScanBehavior(Behavior):
    """
    Vigilant, attentive posture.
    Triggered by investigation goals and suspicious emotions.
    """

    def __init__(self):
        super().__init__("AlertScan")

    def calculate_utility(self, cognitive_state: CognitiveState, body_state: BodyState) -> float:
        utility = 0.0

        # Match investigative goals
        if cognitive_state.goal in ["investigate", "alert_scan", "search"]:
            utility += 0.6

        # Match suspicious/curious emotions
        if cognitive_state.emotion in ["suspicious", "curious", "protective"]:
            utility += 0.3

        # Medium urgency preferred
        if 0.3 <= cognitive_state.urgency <= 0.7:
            utility += 0.1

        return utility * cognitive_state.confidence

    def execute(self, cognitive_state: CognitiveState, body_state: BodyState) -> BodyCommand:
        return BodyCommand(
            posture=Posture.ALERT,
            luminance=Luminance.BRIGHT,
            left_hand=HandState.POINTING,  # Ready to indicate
            right_hand=HandState.POINTING,
            attention_target=cognitive_state.focus,
            duration=3.0
        )


class RelaxedIdleBehavior(Behavior):
    """
    Neutral, resting posture.
    Default behavior when no specific goal is active.
    """

    def __init__(self):
        super().__init__("RelaxedIdle")

    def calculate_utility(self, cognitive_state: CognitiveState, body_state: BodyState) -> float:
        utility = 0.0

        # Match idle goal
        if cognitive_state.goal == "idle":
            utility += 0.5

        # Match neutral emotion
        if cognitive_state.emotion == "neutral":
            utility += 0.3

        # Low urgency preferred
        if cognitive_state.urgency < 0.3:
            utility += 0.2

        # Always a fallback option (base utility)
        utility += 0.1

        return utility

    def execute(self, cognitive_state: CognitiveState, body_state: BodyState) -> BodyCommand:
        return BodyCommand(
            posture=Posture.IDLE,
            luminance=Luminance.DIM,
            left_hand=HandState.RELAXED,
            right_hand=HandState.RELAXED,
            attention_target=None,
            duration=5.0
        )


class CuriousExploreBehavior(Behavior):
    """
    Inquisitive, investigating posture.
    Triggered by curiosity and exploration goals.
    """

    def __init__(self):
        super().__init__("CuriousExplore")

    def calculate_utility(self, cognitive_state: CognitiveState, body_state: BodyState) -> float:
        utility = 0.0

        # Match exploration goals
        if cognitive_state.goal in ["investigate", "search", "explore"]:
            utility += 0.5

        # Strong match for curiosity
        if cognitive_state.emotion == "curious":
            utility += 0.4

        # Medium urgency
        if 0.2 <= cognitive_state.urgency <= 0.6:
            utility += 0.1

        return utility * cognitive_state.confidence

    def execute(self, cognitive_state: CognitiveState, body_state: BodyState) -> BodyCommand:
        return BodyCommand(
            posture=Posture.CURIOUS,
            luminance=Luminance.NORMAL,
            left_hand=HandState.POINTING,  # Reaching out
            right_hand=HandState.OPEN,
            attention_target=cognitive_state.focus,
            duration=2.5
        )


class ProtectiveBehavior(Behavior):
    """
    Defensive, guarding posture.
    Triggered by protective goals and threat detection.
    """

    def __init__(self):
        super().__init__("Protective")

    def calculate_utility(self, cognitive_state: CognitiveState, body_state: BodyState) -> float:
        utility = 0.0

        # Strong match for protective goals
        if cognitive_state.goal in ["protect", "guard"]:
            utility += 0.7

        # Match protective emotion
        if cognitive_state.emotion in ["protective", "suspicious"]:
            utility += 0.2

        # Urgency is important
        utility += cognitive_state.urgency * 0.2

        return utility * cognitive_state.confidence

    def execute(self, cognitive_state: CognitiveState, body_state: BodyState) -> BodyCommand:
        return BodyCommand(
            posture=Posture.ALERT,
            luminance=Luminance.BRIGHT,
            left_hand=HandState.CLOSED,  # Ready to defend
            right_hand=HandState.OPEN,
            attention_target=cognitive_state.focus,
            duration=3.0
        )


class PlayfulBehavior(Behavior):
    """
    Light-hearted, teasing posture.
    Triggered by playful emotions and joking goals.
    """

    def __init__(self):
        super().__init__("Playful")

    def calculate_utility(self, cognitive_state: CognitiveState, body_state: BodyState) -> float:
        utility = 0.0

        # Match playful goals
        if cognitive_state.goal in ["playful_tease", "greet"]:
            utility += 0.5

        # Strong match for playful emotion
        if cognitive_state.emotion in ["playful", "mischievous"]:
            utility += 0.4

        # Low urgency preferred
        if cognitive_state.urgency < 0.4:
            utility += 0.1

        return utility * cognitive_state.confidence

    def execute(self, cognitive_state: CognitiveState, body_state: BodyState) -> BodyCommand:
        return BodyCommand(
            posture=Posture.RELAXED,
            luminance=Luminance.SOFT,
            left_hand=HandState.OPEN,
            right_hand=HandState.POINTING,  # Playful gesture
            attention_target=cognitive_state.focus,
            duration=2.0
        )


class IlluminateBehavior(Behavior):
    """
    Specialized behavior for providing light.
    Triggered by illumination goals.
    """

    def __init__(self):
        super().__init__("Illuminate")

    def calculate_utility(self, cognitive_state: CognitiveState, body_state: BodyState) -> float:
        utility = 0.0

        # Very strong match for illumination goal
        if cognitive_state.goal == "provide_illumination":
            utility += 0.9

        # Helpful emotion is good
        if cognitive_state.emotion in ["friendly", "helpful"]:
            utility += 0.1

        return utility * cognitive_state.confidence

    def execute(self, cognitive_state: CognitiveState, body_state: BodyState) -> BodyCommand:
        # Choose luminance based on urgency
        if cognitive_state.urgency > 0.6:
            luminance = Luminance.INTENSE
        else:
            luminance = Luminance.BRIGHT

        return BodyCommand(
            posture=Posture.RELAXED,
            luminance=luminance,
            left_hand=HandState.OPEN,
            right_hand=HandState.OPEN,
            attention_target=None,
            duration=3.0
        )


# ============================================================================
# BEHAVIOR ARBITER
# ============================================================================

class BehaviorArbiter:
    """
    Selects and executes behaviors based on cognitive state.

    Uses utility-based selection: each behavior calculates a utility score,
    and the behavior with the highest score is executed.
    """

    def __init__(self):
        # Initialize behavior library
        self.behaviors: List[Behavior] = [
            IntimidateBehavior(),
            FriendlyGreetBehavior(),
            AlertScanBehavior(),
            RelaxedIdleBehavior(),
            CuriousExploreBehavior(),
            ProtectiveBehavior(),
            PlayfulBehavior(),
            IlluminateBehavior(),
        ]

        # Behavior selection history (for debugging)
        self.selection_history: List[Dict[str, Any]] = []
        self.max_history = 50

    def select_and_execute(
        self,
        cognitive_state: CognitiveState,
        body_state: BodyState
    ) -> BodyCommand:
        """
        Select the best behavior and execute it.

        Args:
            cognitive_state: Current cognitive state from LLM
            body_state: Current body configuration

        Returns:
            BodyCommand to apply to the virtual body
        """
        # Calculate utilities for all behaviors
        utilities = []
        for behavior in self.behaviors:
            utility = behavior.calculate_utility(cognitive_state, body_state)
            utilities.append((behavior, utility))

        # Sort by utility (descending)
        utilities.sort(key=lambda x: x[1], reverse=True)

        # Select behavior with highest utility
        selected_behavior, selected_utility = utilities[0]

        # Log selection
        self._log_selection(cognitive_state, utilities, selected_behavior, selected_utility)

        # Execute behavior
        command = selected_behavior.execute(cognitive_state, body_state)

        return command

    def _log_selection(
        self,
        cognitive_state: CognitiveState,
        utilities: List[tuple],
        selected: Behavior,
        utility: float
    ) -> None:
        """Log behavior selection for debugging"""
        from datetime import datetime

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "cognitive_state": cognitive_state.to_dict(),
            "selected_behavior": selected.name,
            "selected_utility": utility,
            "all_utilities": [(b.name, u) for b, u in utilities[:5]]  # Top 5
        }

        self.selection_history.append(log_entry)

        # Limit history size
        if len(self.selection_history) > self.max_history:
            self.selection_history.pop(0)

        # Debug print
        print(f"[BEHAVIOR] Selected: {selected.name} (utility={utility:.2f})")
        print(f"[BEHAVIOR]   Goal: {cognitive_state.goal}, Emotion: {cognitive_state.emotion}")
        print(f"[BEHAVIOR]   Top alternatives: {[(b.name, f'{u:.2f}') for b, u in utilities[1:4]]}")

    def get_selection_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent behavior selection history"""
        return self.selection_history[-limit:]

    def get_available_behaviors(self) -> List[str]:
        """Get list of available behavior names"""
        return [b.name for b in self.behaviors]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def describe_behavior_library() -> Dict[str, str]:
    """
    Get descriptions of all available behaviors.

    Returns:
        Dictionary mapping behavior names to descriptions
    """
    return {
        "Intimidate": "Threatening, aggressive posture with intense luminance",
        "FriendlyGreet": "Warm, welcoming posture with soft glow",
        "AlertScan": "Vigilant, attentive posture with bright light",
        "RelaxedIdle": "Neutral, resting posture with dim light",
        "CuriousExplore": "Inquisitive, investigating posture",
        "Protective": "Defensive, guarding posture",
        "Playful": "Light-hearted, teasing posture",
        "Illuminate": "Specialized behavior for providing light"
    }


# ============================================================================
# EXAMPLE USAGE (for testing)
# ============================================================================

if __name__ == "__main__":
    from virtual_body import VirtualWorld

    # Create arbiter and virtual world
    arbiter = BehaviorArbiter()
    world = VirtualWorld()

    print("=== Behavior System Test ===\n")

    # Test 1: Intimidation scenario
    print("Test 1: Intimidation")
    cognitive = CognitiveState(
        goal="intimidate",
        emotion="hostile",
        confidence=0.9,
        urgency=0.8,
        focus="intruder_1",
        dialogue="Back off, pal."
    )

    command = arbiter.select_and_execute(cognitive, world.get_body_state())
    world.update_body(command)
    print(f"Result: {world.get_body_state().to_dict()}\n")

    # Test 2: Friendly greeting
    print("Test 2: Friendly Greeting")
    cognitive = CognitiveState(
        goal="greet",
        emotion="friendly",
        confidence=1.0,
        urgency=0.3,
        dialogue="Hey there!"
    )

    command = arbiter.select_and_execute(cognitive, world.get_body_state())
    world.update_body(command)
    print(f"Result: {world.get_body_state().to_dict()}\n")

    # Test 3: Idle state
    print("Test 3: Idle")
    cognitive = CognitiveState(
        goal="idle",
        emotion="neutral",
        confidence=0.5,
        urgency=0.1,
        dialogue="..."
    )

    command = arbiter.select_and_execute(cognitive, world.get_body_state())
    world.update_body(command)
    print(f"Result: {world.get_body_state().to_dict()}\n")

    # Show history
    print("Selection History:")
    for entry in arbiter.get_selection_history():
        print(f"  {entry['timestamp']}: {entry['selected_behavior']}")
