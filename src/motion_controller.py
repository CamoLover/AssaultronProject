"""
Motion Controller - Hardware Translation Layer

This module translates high-level body states and commands into concrete
hardware primitives (LED intensity, hand positions, etc.).

This is the ONLY layer that knows about hardware specifics. All other layers
operate purely on symbolic states.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .virtual_body import BodyState, BodyCommand, Posture, Luminance, HandState


# ============================================================================
# HARDWARE MAPPINGS
# ============================================================================

# Map symbolic postures to hand positions (0-100)
POSTURE_TO_HANDS = {
    Posture.IDLE: {"left": 0, "right": 0},         # Hands at rest/closed
    Posture.ALERT: {"left": 30, "right": 30},      # Slightly open, ready
    Posture.AGGRESSIVE: {"left": 0, "right": 0},   # Fists clenched
    Posture.RELAXED: {"left": 50, "right": 50},    # Hands open, calm
    Posture.CURIOUS: {"left": 70, "right": 70}     # Hands extended
}

# Map symbolic luminance to LED intensity (0-100)
LUMINANCE_TO_LED = {
    Luminance.DIM: 10,
    Luminance.SOFT: 35,
    Luminance.NORMAL: 50,
    Luminance.BRIGHT: 75,
    Luminance.INTENSE: 100
}

# Map hand states to position modifiers
HAND_STATE_TO_POSITION = {
    HandState.CLOSED: 0,
    HandState.RELAXED: 30,
    HandState.OPEN: 70,
    HandState.POINTING: 50
}

# Map hand states to status strings (for hardware_state compatibility)
HAND_STATE_TO_STATUS = {
    HandState.CLOSED: "closed",
    HandState.RELAXED: "relaxed",
    HandState.OPEN: "open",
    HandState.POINTING: "pointing"
}


# ============================================================================
# MOTION CONTROLLER
# ============================================================================

class MotionController:
    """
    Translates symbolic body commands into hardware primitives.

    Responsibilities:
    - Map symbolic states to hardware values
    - Apply safety constraints
    - Smooth interpolation (future)
    - Maintain hardware state format for backward compatibility
    """

    def __init__(self, enable_smoothing: bool = False, transition_duration: float = 0.5):
        """
        Initialize motion controller.

        Args:
            enable_smoothing: Enable smooth transitions (future feature)
            transition_duration: Duration of smooth transitions in seconds
        """
        self.enable_smoothing = enable_smoothing
        self.transition_duration = transition_duration

        # Current hardware state (compatible with existing system)
        self.hardware_state = {
            "led_intensity": 50,
            "hands": {
                "left": {"position": 0, "status": "closed"},
                "right": {"position": 0, "status": "closed"}
            }
        }

        # Target state (for smooth interpolation)
        self._target_state = self.hardware_state.copy()
        self._last_update = datetime.now()

        # Safety constraints
        self.led_min = 0
        self.led_max = 100
        self.hand_min = 0
        self.hand_max = 100
        self.max_change_rate = 50  # Max change per second (for rate limiting)

    def apply_body_command(self, command: BodyCommand) -> Dict[str, Any]:
        """
        Translate body command to hardware state.

        Args:
            command: High-level body command

        Returns:
            Updated hardware state dictionary
        """
        # Translate symbolic states to hardware values
        led_intensity = self._map_luminance(command.luminance)
        hand_left_pos, hand_left_status = self._map_hand(command.left_hand, command.posture, "left")
        hand_right_pos, hand_right_status = self._map_hand(command.right_hand, command.posture, "right")

        # Apply safety constraints
        led_intensity = self._clamp(led_intensity, self.led_min, self.led_max)
        hand_left_pos = self._clamp(hand_left_pos, self.hand_min, self.hand_max)
        hand_right_pos = self._clamp(hand_right_pos, self.hand_min, self.hand_max)

        # Update hardware state
        if self.enable_smoothing:
            # Set target and interpolate gradually (future feature)
            self._target_state = {
                "led_intensity": led_intensity,
                "hands": {
                    "left": {"position": hand_left_pos, "status": hand_left_status},
                    "right": {"position": hand_right_pos, "status": hand_right_status}
                }
            }
            self._interpolate_to_target()
        else:
            # Immediate update
            self.hardware_state["led_intensity"] = led_intensity
            self.hardware_state["hands"]["left"]["position"] = hand_left_pos
            self.hardware_state["hands"]["left"]["status"] = hand_left_status
            self.hardware_state["hands"]["right"]["position"] = hand_right_pos
            self.hardware_state["hands"]["right"]["status"] = hand_right_status

        self._last_update = datetime.now()

        # Log translation
        print(f"[MOTION] Command -> Hardware:")
        print(f"[MOTION]   {command.posture.value} -> hands L:{hand_left_pos} R:{hand_right_pos}")
        print(f"[MOTION]   {command.luminance.value} -> LED:{led_intensity}")
        print(f"[MOTION]   hands: {command.left_hand.value}/{command.right_hand.value}")

        return self.hardware_state.copy()

    def _map_luminance(self, luminance: Luminance) -> int:
        """Map symbolic luminance to LED intensity"""
        return LUMINANCE_TO_LED.get(luminance, 50)

    def _map_hand(self, hand_state: HandState, posture: Posture, side: str) -> tuple:
        """
        Map hand state and posture to position and status.

        Args:
            hand_state: Symbolic hand state
            posture: Overall body posture (influences hand position)
            side: "left" or "right"

        Returns:
            (position, status_string)
        """
        # Base position from posture
        base_position = POSTURE_TO_HANDS.get(posture, {"left": 30, "right": 30})[side]

        # Modifier from hand state
        hand_position = HAND_STATE_TO_POSITION.get(hand_state, 30)

        # Combine: average of posture and hand state
        # (You can tune this formula based on desired behavior)
        final_position = int((base_position + hand_position) / 2)

        # Status string
        status = HAND_STATE_TO_STATUS.get(hand_state, "relaxed")

        return final_position, status

    def _clamp(self, value: float, min_val: float, max_val: float) -> int:
        """Clamp value to range and convert to int"""
        return int(max(min_val, min(max_val, value)))

    def _interpolate_to_target(self) -> None:
        """
        Gradually interpolate current state toward target state.

        This implements smooth motion transitions. Currently a placeholder
        for future enhancement - would require continuous update loop.
        """
        # TODO: Implement smooth interpolation
        # For now, just snap to target
        self.hardware_state = self._target_state.copy()

    def get_hardware_state(self) -> Dict[str, Any]:
        """Get current hardware state"""
        return self.hardware_state.copy()

    def reset_hardware(self) -> None:
        """Reset hardware to safe default state"""
        self.hardware_state = {
            "led_intensity": 10,
            "hands": {
                "left": {"position": 0, "status": "closed"},
                "right": {"position": 0, "status": "closed"}
            }
        }
        print("[MOTION] Hardware reset to safe defaults")


# ============================================================================
# BODY STATE SYNCHRONIZATION
# ============================================================================

class BodyStateTranslator:
    """
    Bidirectional translator between virtual body states and hardware states.

    Allows reading hardware state back into virtual body representation
    (useful for debugging and state verification).
    """

    @staticmethod
    def hardware_to_body_state(hardware_state: Dict[str, Any]) -> BodyState:
        """
        Convert hardware state to virtual body state.

        Args:
            hardware_state: Hardware state dict

        Returns:
            Estimated BodyState
        """
        # Map LED intensity to luminance
        led = hardware_state.get("led_intensity", 50)
        if led < 20:
            luminance = Luminance.DIM
        elif led < 40:
            luminance = Luminance.SOFT
        elif led < 65:
            luminance = Luminance.NORMAL
        elif led < 85:
            luminance = Luminance.BRIGHT
        else:
            luminance = Luminance.INTENSE

        # Map hand positions to states
        hands = hardware_state.get("hands", {})
        left_pos = hands.get("left", {}).get("position", 0)
        right_pos = hands.get("right", {}).get("position", 0)

        left_hand = BodyStateTranslator._position_to_hand_state(left_pos)
        right_hand = BodyStateTranslator._position_to_hand_state(right_pos)

        # Infer posture from hand positions
        avg_pos = (left_pos + right_pos) / 2
        if avg_pos < 15:
            posture = Posture.IDLE
        elif avg_pos < 35:
            posture = Posture.ALERT
        elif avg_pos < 60:
            posture = Posture.RELAXED
        else:
            posture = Posture.CURIOUS

        return BodyState(
            posture=posture,
            luminance=luminance,
            left_hand=left_hand,
            right_hand=right_hand
        )

    @staticmethod
    def _position_to_hand_state(position: int) -> HandState:
        """Convert hand position to hand state"""
        if position < 15:
            return HandState.CLOSED
        elif position < 45:
            return HandState.RELAXED
        elif position < 65:
            return HandState.POINTING
        else:
            return HandState.OPEN


# ============================================================================
# HARDWARE STATE VALIDATOR
# ============================================================================

class HardwareStateValidator:
    """
    Validates hardware state for safety and correctness.
    """

    @staticmethod
    def validate(hardware_state: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate hardware state.

        Args:
            hardware_state: Hardware state dict to validate

        Returns:
            (is_valid, error_message)
        """
        # Check LED intensity
        led = hardware_state.get("led_intensity")
        if led is None:
            return False, "Missing led_intensity"
        if not (0 <= led <= 100):
            return False, f"LED intensity {led} out of range [0, 100]"

        # Check hands
        hands = hardware_state.get("hands")
        if hands is None:
            return False, "Missing hands"

        for side in ["left", "right"]:
            if side not in hands:
                return False, f"Missing hand: {side}"

            hand = hands[side]
            if "position" not in hand:
                return False, f"Missing position for {side} hand"
            if "status" not in hand:
                return False, f"Missing status for {side} hand"

            pos = hand["position"]
            if not (0 <= pos <= 100):
                return False, f"{side} hand position {pos} out of range [0, 100]"

            status = hand["status"]
            if status not in ["closed", "relaxed", "open", "pointing"]:
                return False, f"Invalid {side} hand status: {status}"

        return True, None


# ============================================================================
# EXAMPLE USAGE (for testing)
# ============================================================================

if __name__ == "__main__":
    from virtual_body import BodyCommand, Posture, Luminance, HandState

    # Create motion controller
    controller = MotionController()

    print("=== Motion Controller Test ===\n")

    # Test 1: Aggressive posture
    print("Test 1: Aggressive posture")
    command = BodyCommand(
        posture=Posture.AGGRESSIVE,
        luminance=Luminance.INTENSE,
        left_hand=HandState.CLOSED,
        right_hand=HandState.CLOSED,
        duration=2.0
    )

    hardware = controller.apply_body_command(command)
    print(f"Hardware State: {hardware}\n")

    # Validate
    valid, error = HardwareStateValidator.validate(hardware)
    print(f"Valid: {valid}, Error: {error}\n")

    # Test 2: Friendly posture
    print("Test 2: Friendly posture")
    command = BodyCommand(
        posture=Posture.RELAXED,
        luminance=Luminance.SOFT,
        left_hand=HandState.OPEN,
        right_hand=HandState.OPEN,
        duration=2.0
    )

    hardware = controller.apply_body_command(command)
    print(f"Hardware State: {hardware}\n")

    # Test 3: Reverse translation
    print("Test 3: Hardware → Body State")
    body_state = BodyStateTranslator.hardware_to_body_state(hardware)
    print(f"Body State: {body_state.to_dict()}\n")

    # Test 4: Reset
    print("Test 4: Reset")
    controller.reset_hardware()
    print(f"Hardware State: {controller.get_hardware_state()}")
