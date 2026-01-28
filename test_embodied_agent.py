"""
Integration Tests for Embodied Agent Architecture

This module provides tests to validate the embodied agent system,
including cognitive processing, behavior selection, and motion translation.
"""

import sys
import json
from datetime import datetime

# Import all layers
from virtual_body import (
    VirtualWorld, BodyState, WorldState, CognitiveState, BodyCommand,
    Posture, Luminance, HandState, Environment, ThreatLevel,
    analyze_user_message_for_world_cues
)
from cognitive_layer import CognitiveEngine, extract_memory_from_message
from behavioral_layer import BehaviorArbiter
from motion_controller import MotionController, HardwareStateValidator
from config import Config


# ============================================================================
# TEST UTILITIES
# ============================================================================

class TestReport:
    """Simple test reporting utility"""

    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []

    def test(self, name, condition, message=""):
        """Run a test assertion"""
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"[PASS] {name}")
        else:
            self.tests_failed += 1
            self.failures.append(f"{name}: {message}")
            print(f"[FAIL] {name}: {message}")

    def summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print(f"TESTS RUN: {self.tests_run}")
        print(f"PASSED: {self.tests_passed}")
        print(f"FAILED: {self.tests_failed}")
        print("="*60)

        if self.failures:
            print("\nFAILURES:")
            for failure in self.failures:
                print(f"  - {failure}")

        return self.tests_failed == 0


# ============================================================================
# UNIT TESTS
# ============================================================================

def test_virtual_body(report: TestReport):
    """Test virtual body and world model"""
    print("\n--- Testing Virtual Body ---")

    world = VirtualWorld()

    # Test initial state
    body = world.get_body_state()
    report.test(
        "Virtual body initializes with idle state",
        body.posture == Posture.IDLE and body.luminance == Luminance.DIM
    )

    # Test body command application
    command = BodyCommand(
        posture=Posture.ALERT,
        luminance=Luminance.BRIGHT,
        left_hand=HandState.POINTING,
        right_hand=HandState.POINTING,
        duration=2.0
    )

    world.update_body(command)
    body = world.get_body_state()

    report.test(
        "Body command updates body state correctly",
        body.posture == Posture.ALERT and
        body.luminance == Luminance.BRIGHT and
        body.left_hand == HandState.POINTING
    )

    # Test world state update
    world.update_world(environment="dark", threat_level="high")
    world_state = world.get_world_state()

    report.test(
        "World state updates correctly",
        world_state.environment == Environment.DARK and
        world_state.threat_level == ThreatLevel.HIGH
    )

    # Test history tracking
    history = world.get_history()
    report.test(
        "State history is tracked",
        len(history) > 0
    )


def test_behavior_selection(report: TestReport):
    """Test behavior selection logic"""
    print("\n--- Testing Behavior Selection ---")

    arbiter = BehaviorArbiter()
    body_state = BodyState()

    # Test intimidation behavior
    cognitive = CognitiveState(
        goal="intimidate",
        emotion="hostile",
        confidence=0.9,
        urgency=0.8,
        dialogue="Back off, pal."
    )

    command = arbiter.select_and_execute(cognitive, body_state)

    report.test(
        "Intimidation goal triggers aggressive posture",
        command.posture == Posture.AGGRESSIVE and
        command.luminance == Luminance.INTENSE
    )

    # Test friendly behavior
    cognitive = CognitiveState(
        goal="greet",
        emotion="friendly",
        confidence=1.0,
        urgency=0.3,
        dialogue="Hey there!"
    )

    command = arbiter.select_and_execute(cognitive, body_state)

    report.test(
        "Greeting goal triggers relaxed posture",
        command.posture == Posture.RELAXED and
        command.luminance == Luminance.SOFT
    )

    # Test idle behavior
    cognitive = CognitiveState(
        goal="idle",
        emotion="neutral",
        confidence=0.5,
        urgency=0.1,
        dialogue=""
    )

    command = arbiter.select_and_execute(cognitive, body_state)

    report.test(
        "Idle goal triggers idle posture",
        command.posture == Posture.IDLE and
        command.luminance == Luminance.DIM
    )

    # Test illumination behavior
    cognitive = CognitiveState(
        goal="provide_illumination",
        emotion="friendly",
        confidence=0.9,
        urgency=0.5,
        dialogue="Let me light things up."
    )

    command = arbiter.select_and_execute(cognitive, body_state)

    report.test(
        "Illumination goal triggers bright luminance",
        command.luminance in [Luminance.BRIGHT, Luminance.INTENSE]
    )


def test_motion_translation(report: TestReport):
    """Test motion controller hardware translation"""
    print("\n--- Testing Motion Translation ---")

    controller = MotionController()

    # Test aggressive posture translation
    command = BodyCommand(
        posture=Posture.AGGRESSIVE,
        luminance=Luminance.INTENSE,
        left_hand=HandState.CLOSED,
        right_hand=HandState.CLOSED,
        duration=2.0
    )

    hardware = controller.apply_body_command(command)

    report.test(
        "Aggressive posture translates to hardware",
        hardware["led_intensity"] == 100 and
        hardware["hands"]["left"]["status"] == "closed" and
        hardware["hands"]["right"]["status"] == "closed"
    )

    # Test friendly posture translation
    command = BodyCommand(
        posture=Posture.RELAXED,
        luminance=Luminance.SOFT,
        left_hand=HandState.OPEN,
        right_hand=HandState.OPEN,
        duration=2.0
    )

    hardware = controller.apply_body_command(command)

    report.test(
        "Friendly posture translates to hardware",
        hardware["led_intensity"] == 35 and
        hardware["hands"]["left"]["status"] == "open"
    )

    # Test hardware validation
    valid, error = HardwareStateValidator.validate(hardware)
    report.test(
        "Hardware state passes validation",
        valid and error is None,
        error if error else ""
    )

    # Test invalid hardware state
    invalid_hardware = {
        "led_intensity": 150,  # Out of range
        "hands": {}
    }

    valid, error = HardwareStateValidator.validate(invalid_hardware)
    report.test(
        "Invalid hardware state is detected",
        not valid and error is not None
    )


def test_world_cue_analysis(report: TestReport):
    """Test user message analysis for world cues"""
    print("\n--- Testing World Cue Analysis ---")

    # Test darkness detection
    updates = analyze_user_message_for_world_cues("It's too dark in here!")
    report.test(
        "Darkness cue detected",
        updates.get("environment") == "dark"
    )

    # Test brightness detection
    updates = analyze_user_message_for_world_cues("It's way too bright!")
    report.test(
        "Brightness cue detected",
        updates.get("environment") == "bright"
    )

    # Test threat detection
    updates = analyze_user_message_for_world_cues("Help! There's an intruder!")
    report.test(
        "Threat cue detected",
        updates.get("threat_level") == "high"
    )

    # Test no cues
    updates = analyze_user_message_for_world_cues("How are you doing today?")
    report.test(
        "No cues in neutral message",
        len(updates) == 0
    )


def test_memory_extraction(report: TestReport):
    """Test memory extraction from conversations"""
    print("\n--- Testing Memory Extraction ---")

    # Test name extraction
    memory = extract_memory_from_message("Hi, my name is John", "Nice to meet you!")
    report.test(
        "Name extracted from message",
        memory is not None and "John" in memory["content"]
    )

    # Test remember instruction
    memory = extract_memory_from_message("Remember that I like coffee", "Got it!")
    report.test(
        "Remember instruction captured",
        memory is not None and memory["type"] == "user_instruction"
    )

    # Test preference extraction
    memory = extract_memory_from_message("I like robots", "Interesting!")
    report.test(
        "User preference captured",
        memory is not None and memory["type"] == "user_preference"
    )

    # Test no memorable content
    memory = extract_memory_from_message("What time is it?", "It's 3pm")
    report.test(
        "Non-memorable message returns None",
        memory is None
    )


def test_cognitive_state_creation(report: TestReport):
    """Test CognitiveState object creation and validation"""
    print("\n--- Testing Cognitive State ---")

    # Test valid cognitive state
    state = CognitiveState(
        goal="greet",
        emotion="friendly",
        confidence=0.8,
        urgency=0.4,
        focus=None,
        dialogue="Hello there!"
    )

    report.test(
        "CognitiveState created successfully",
        state.goal == "greet" and state.emotion == "friendly"
    )

    # Test confidence clamping
    state = CognitiveState(
        goal="test",
        emotion="neutral",
        confidence=1.5,  # Out of range
        urgency=-0.1,    # Out of range
        dialogue=""
    )

    report.test(
        "Confidence and urgency are clamped to [0, 1]",
        0.0 <= state.confidence <= 1.0 and
        0.0 <= state.urgency <= 1.0
    )

    # Test serialization
    state_dict = state.to_dict()
    report.test(
        "CognitiveState serializes to dict",
        isinstance(state_dict, dict) and "goal" in state_dict
    )

    # Test deserialization
    restored = CognitiveState.from_dict(state_dict)
    report.test(
        "CognitiveState deserializes from dict",
        restored.goal == state.goal and restored.emotion == state.emotion
    )


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_full_pipeline_dark_room(report: TestReport):
    """Test complete pipeline: dark room scenario"""
    print("\n--- Testing Full Pipeline: Dark Room ---")

    world = VirtualWorld()
    arbiter = BehaviorArbiter()
    controller = MotionController()

    # Simulate user input: "It's dark in here"
    user_message = "It's too dark in here"

    # Step 1: Update world
    world_updates = analyze_user_message_for_world_cues(user_message)
    world.update_world(**world_updates)

    report.test(
        "World detects dark environment",
        world.get_world_state().environment == Environment.DARK
    )

    # Step 2: Simulate cognitive state (would come from LLM)
    cognitive = CognitiveState(
        goal="provide_illumination",
        emotion="friendly",
        confidence=0.9,
        urgency=0.5,
        dialogue="Too dark for you? Let me light things up."
    )

    # Step 3: Select behavior
    command = arbiter.select_and_execute(cognitive, world.get_body_state())

    report.test(
        "Behavior selected for illumination",
        command.luminance in [Luminance.BRIGHT, Luminance.INTENSE]
    )

    # Step 4: Translate to hardware
    hardware = controller.apply_body_command(command)

    report.test(
        "Hardware LED set to bright",
        hardware["led_intensity"] >= 75
    )

    # Step 5: Update virtual body
    world.update_body(command)

    report.test(
        "Virtual body updated with new state",
        world.get_body_state().luminance in [Luminance.BRIGHT, Luminance.INTENSE]
    )


def test_full_pipeline_threat(report: TestReport):
    """Test complete pipeline: threat scenario"""
    print("\n--- Testing Full Pipeline: Threat Detection ---")

    world = VirtualWorld()
    arbiter = BehaviorArbiter()
    controller = MotionController()

    # Simulate user input: threat detected
    user_message = "Help! I think someone's breaking in!"

    # Step 1: Update world
    world_updates = analyze_user_message_for_world_cues(user_message)
    world.update_world(**world_updates)

    report.test(
        "World detects high threat",
        world.get_world_state().threat_level == ThreatLevel.HIGH
    )

    # Step 2: Simulate cognitive state
    cognitive = CognitiveState(
        goal="protect",
        emotion="hostile",
        confidence=0.85,
        urgency=0.9,
        focus="intruder_1",
        dialogue="Stay behind me. Nobody messes with my human."
    )

    # Step 3: Select behavior
    command = arbiter.select_and_execute(cognitive, world.get_body_state())

    report.test(
        "Protective/aggressive behavior selected",
        command.posture in [Posture.ALERT, Posture.AGGRESSIVE]
    )

    # Step 4: Translate to hardware
    hardware = controller.apply_body_command(command)

    report.test(
        "Hardware in alert/defensive configuration",
        hardware["led_intensity"] >= 75
    )


def test_behavior_transitions(report: TestReport):
    """Test smooth behavior transitions"""
    print("\n--- Testing Behavior Transitions ---")

    world = VirtualWorld()
    arbiter = BehaviorArbiter()

    # Start in idle
    cognitive = CognitiveState(
        goal="idle",
        emotion="neutral",
        confidence=0.5,
        urgency=0.1,
        dialogue=""
    )

    command = arbiter.select_and_execute(cognitive, world.get_body_state())
    world.update_body(command)

    initial_posture = world.get_body_state().posture

    # Transition to alert
    cognitive = CognitiveState(
        goal="investigate",
        emotion="curious",
        confidence=0.7,
        urgency=0.5,
        dialogue="What's that?"
    )

    command = arbiter.select_and_execute(cognitive, world.get_body_state())
    world.update_body(command)

    new_posture = world.get_body_state().posture

    report.test(
        "Behavior transitions from idle to alert/curious",
        initial_posture == Posture.IDLE and
        new_posture in [Posture.ALERT, Posture.CURIOUS]
    )

    # Check history
    history = world.get_history()
    report.test(
        "State transitions are logged",
        len(history) >= 2
    )


# ============================================================================
# ARCHITECTURE VALIDATION
# ============================================================================

def validate_architecture(report: TestReport):
    """Validate overall architecture constraints"""
    print("\n--- Validating Architecture ---")

    # Test layer independence
    world = VirtualWorld()
    arbiter = BehaviorArbiter()
    controller = MotionController()

    report.test(
        "Virtual world can be instantiated independently",
        isinstance(world, VirtualWorld)
    )

    report.test(
        "Behavior arbiter can be instantiated independently",
        isinstance(arbiter, BehaviorArbiter)
    )

    report.test(
        "Motion controller can be instantiated independently",
        isinstance(controller, MotionController)
    )

    # Test that layers don't directly reference each other's internals
    # (This would require deeper inspection, but we can test basic contracts)

    report.test(
        "Behaviors are available",
        len(arbiter.behaviors) > 0
    )

    report.test(
        "Hardware state format is valid",
        "led_intensity" in controller.hardware_state and
        "hands" in controller.hardware_state
    )


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all tests and report results"""
    print("="*60)
    print("EMBODIED AGENT ARCHITECTURE - TEST SUITE")
    print("="*60)

    report = TestReport()

    # Unit tests
    test_virtual_body(report)
    test_behavior_selection(report)
    test_motion_translation(report)
    test_world_cue_analysis(report)
    test_memory_extraction(report)
    test_cognitive_state_creation(report)

    # Integration tests
    test_full_pipeline_dark_room(report)
    test_full_pipeline_threat(report)
    test_behavior_transitions(report)

    # Architecture validation
    validate_architecture(report)

    # Summary
    success = report.summary()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
