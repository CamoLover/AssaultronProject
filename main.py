"""
Assaultron Main Server - Embodied Agent Architecture

This is the refactored main server that implements the behavior-based
embodied agent system. The AI no longer uses tools to directly control
hardware - instead it reasons about goals and emotions, which are then
translated through behavioral and motion layers.
"""

from flask import Flask, render_template, request, jsonify
import threading
import time
import json
from datetime import datetime
import requests
from config import Config
import psutil
from voicemanager import VoiceManager

# Import new embodied agent layers
from virtual_body import (
    VirtualWorld, BodyState, WorldState, CognitiveState, BodyCommand,
    analyze_user_message_for_world_cues
)
from cognitive_layer import CognitiveEngine, extract_memory_from_message
from behavioral_layer import BehaviorArbiter, describe_behavior_library
from motion_controller import MotionController, HardwareStateValidator


app = Flask(__name__)
config = Config()


# ============================================================================
# EMBODIED ASSAULTRON CORE
# ============================================================================

class EmbodiedAssaultronCore:
    """
    Main Assaultron system using embodied agent architecture.

    Architecture layers:
    1. Cognitive Layer: LLM reasoning about goals/emotions
    2. Behavioral Layer: Selects behaviors based on cognitive state
    3. Virtual Body: Maintains symbolic body state
    4. Motion Controller: Translates symbolic states to hardware
    """

    def __init__(self):
        # System state
        self.system_logs = []
        self.status = "Initializing..."
        self.ai_active = False
        self.start_time = datetime.now()
        self.performance_stats = {
            "total_requests": 0,
            "avg_response_time": 0,
            "last_response_time": 0
        }

        # Initialize embodied agent layers
        self.log_event("Initializing Embodied Agent Architecture...", "SYSTEM")

        # Virtual World (body + environment)
        self.virtual_world = VirtualWorld()
        self.log_event("Virtual World initialized", "SYSTEM")

        # Cognitive Layer (LLM interface)
        self.cognitive_engine = CognitiveEngine(
            ollama_url=Config.OLLAMA_URL,
            model=Config.AI_MODEL,
            system_prompt=Config.ASSAULTRON_PROMPT
        )
        self.log_event("Cognitive Engine initialized", "SYSTEM")

        # Behavioral Layer (behavior selection)
        self.behavior_arbiter = BehaviorArbiter()
        self.log_event(f"Behavior Arbiter initialized with {len(self.behavior_arbiter.behaviors)} behaviors", "SYSTEM")

        # Motion Controller (hardware translation)
        self.motion_controller = MotionController()
        self.log_event("Motion Controller initialized", "SYSTEM")

        # Voice system
        self.voice_system = VoiceManager(logger=self)
        self.voice_enabled = False
        self.log_event("Voice Manager initialized", "SYSTEM")

    def log_event(self, message, event_type="INFO"):
        """Log system events"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "type": event_type,
            "message": message
        }
        self.system_logs.append(log_entry)

        # Limit log size
        if len(self.system_logs) > 1000:
            self.system_logs = self.system_logs[-1000:]

        print(f"[{timestamp}] {event_type}: {message}")

    def process_message(self, user_message: str) -> dict:
        """
        Process user message through the embodied agent pipeline.

        Pipeline:
        1. Update world state based on user message cues
        2. Cognitive Layer: LLM generates CognitiveState
        3. Behavioral Layer: Select and execute behavior
        4. Motion Controller: Translate to hardware
        5. Update virtual body
        6. Voice synthesis (if enabled)

        Returns:
            Dictionary with response, hardware state, and metadata
        """
        start_time = time.time()

        try:
            # Step 1: Analyze user message for world cues
            world_updates = analyze_user_message_for_world_cues(user_message)
            if world_updates:
                self.virtual_world.update_world(**world_updates)
                self.log_event(f"World state updated: {world_updates}", "WORLD")

            # Get current states
            world_state = self.virtual_world.get_world_state()
            body_state = self.virtual_world.get_body_state()

            # Step 2: Cognitive Layer - Generate intent
            self.log_event("Cognitive processing...", "COGNITIVE")
            memory_summary = self.cognitive_engine.get_memory_summary()

            cognitive_state = self.cognitive_engine.process_input(
                user_message=user_message,
                world_state=world_state,
                body_state=body_state,
                memory_summary=memory_summary
            )

            self.log_event(
                f"Cognitive state: goal={cognitive_state.goal}, emotion={cognitive_state.emotion}",
                "COGNITIVE"
            )

            # Step 3: Behavioral Layer - Select behavior
            self.log_event("Behavior selection...", "BEHAVIOR")

            body_command = self.behavior_arbiter.select_and_execute(
                cognitive_state=cognitive_state,
                body_state=body_state
            )

            # Step 4: Motion Controller - Translate to hardware
            self.log_event("Motion translation...", "MOTION")

            hardware_state = self.motion_controller.apply_body_command(body_command)

            # Validate hardware state
            is_valid, error = HardwareStateValidator.validate(hardware_state)
            if not is_valid:
                self.log_event(f"Hardware validation failed: {error}", "ERROR")

            # Step 5: Update virtual body
            self.virtual_world.update_body(body_command)

            # Step 6: Extract and store memories
            memory = extract_memory_from_message(user_message, cognitive_state.dialogue)
            if memory:
                self.cognitive_engine.add_memory(memory)
                self.log_event(f"Memory stored: {memory['content']}", "MEMORY")

            # Calculate performance metrics
            response_time = round((time.time() - start_time) * 1000)
            self.performance_stats["total_requests"] += 1
            self.performance_stats["last_response_time"] = response_time

            if self.performance_stats["avg_response_time"] == 0:
                self.performance_stats["avg_response_time"] = response_time
            else:
                self.performance_stats["avg_response_time"] = round(
                    (self.performance_stats["avg_response_time"] + response_time) / 2
                )

            self.log_event(f"Response generated in {response_time}ms", "SYSTEM")

            # Step 7: Voice synthesis (if enabled)
            if self.voice_enabled:
                self.voice_system.synthesize_async(cognitive_state.dialogue)

            # Return complete response
            return {
                "success": True,
                "dialogue": cognitive_state.dialogue,
                "cognitive_state": cognitive_state.to_dict(),
                "body_command": body_command.to_dict(),
                "hardware_state": hardware_state,
                "body_state": body_state.to_dict(),
                "world_state": world_state.to_dict(),
                "response_time": response_time,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            response_time = round((time.time() - start_time) * 1000)
            error_msg = f"Processing failed: {str(e)}"
            self.log_event(error_msg, "ERROR")

            import traceback
            traceback.print_exc()

            return {
                "success": False,
                "error": error_msg,
                "dialogue": "System error. Give me a moment to recalibrate.",
                "response_time": response_time,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

    def initialize_ai(self):
        """Initialize AI connection"""
        try:
            self.log_event("Initializing AI connection...", "SYSTEM")
            response = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=10)
            if response.status_code == 200:
                self.ai_active = True
                self.status = "AI Online - Embodied Agent Ready"
                self.log_event("AI connection established successfully", "SYSTEM")
            else:
                self.status = "AI Connection Failed"
                self.log_event("Failed to connect to Ollama", "ERROR")
        except Exception as e:
            self.status = "AI Connection Failed"
            self.log_event(f"AI initialization error: {str(e)}", "ERROR")

    def get_hardware_state(self):
        """Get current hardware state (backward compatible)"""
        return self.motion_controller.get_hardware_state()

    def set_hardware_manual(self, led_intensity=None, hand_left=None, hand_right=None):
        """
        Manually override hardware state.

        This is for manual control via web UI. It bypasses the embodied
        agent pipeline and directly updates hardware.
        """
        hardware = self.motion_controller.hardware_state

        if led_intensity is not None:
            if 0 <= led_intensity <= 100:
                hardware["led_intensity"] = led_intensity
                self.log_event(f"LED manually set to {led_intensity}%", "MANUAL")

        if hand_left is not None:
            if 0 <= hand_left <= 100:
                hardware["hands"]["left"]["position"] = hand_left
                hardware["hands"]["left"]["status"] = self._position_to_status(hand_left)
                self.log_event(f"Left hand manually set to {hand_left}%", "MANUAL")

        if hand_right is not None:
            if 0 <= hand_right <= 100:
                hardware["hands"]["right"]["position"] = hand_right
                hardware["hands"]["right"]["status"] = self._position_to_status(hand_right)
                self.log_event(f"Right hand manually set to {hand_right}%", "MANUAL")

    def _position_to_status(self, position: int) -> str:
        """Convert position to status string"""
        if position <= 10:
            return "closed"
        elif position <= 40:
            return "relaxed"
        elif position <= 65:
            return "pointing"
        else:
            return "open"


# ============================================================================
# FLASK APPLICATION
# ============================================================================

# Initialize Embodied Assaultron
assaultron = EmbodiedAssaultronCore()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint - processes user message through embodied agent pipeline.
    """
    data = request.get_json()
    message = data.get('message', '').strip()

    if not message:
        return jsonify({"error": "Empty message"}), 400

    # Process through embodied agent pipeline
    result = assaultron.process_message(message)

    if result["success"]:
        # Return response in format compatible with existing web UI
        return jsonify({
            "response": result["dialogue"],
            "timestamp": result["timestamp"],
            "cognitive_state": result.get("cognitive_state"),
            "hardware_state": result.get("hardware_state"),
            "body_state": result.get("body_state")
        })
    else:
        return jsonify({
            "response": result["dialogue"],
            "error": result.get("error"),
            "timestamp": result["timestamp"]
        }), 500


@app.route('/api/logs')
def get_logs():
    """Get system logs"""
    return jsonify(assaultron.system_logs[-50:])


@app.route('/api/status')
def get_status():
    """Get system status"""
    uptime_seconds = (datetime.now() - assaultron.start_time).total_seconds()

    # Get system stats
    try:
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
    except:
        cpu_percent = 0
        memory_percent = 0

    return jsonify({
        "status": assaultron.status,
        "ai_active": assaultron.ai_active,
        "conversation_count": len(assaultron.cognitive_engine.conversation_history),
        "uptime_seconds": int(uptime_seconds),
        "performance": assaultron.performance_stats,
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent
        },
        "architecture": "embodied_agent"
    })


@app.route('/api/history')
def get_history():
    """Get conversation history"""
    history = assaultron.cognitive_engine.get_conversation_history(limit=10)
    return jsonify(history)


@app.route('/api/hardware')
def get_hardware():
    """Get current hardware state (backward compatible)"""
    return jsonify(assaultron.get_hardware_state())


@app.route('/api/memory')
def get_memory():
    """Get AI memory context"""
    memories = assaultron.cognitive_engine.memory_context[-20:]
    return jsonify(memories)


@app.route('/api/hardware/led', methods=['POST'])
def set_led():
    """Manually set LED intensity (bypass embodied agent)"""
    data = request.get_json()
    intensity = data.get('intensity', 50)

    if 0 <= intensity <= 100:
        assaultron.set_hardware_manual(led_intensity=intensity)
        return jsonify({"success": True, "intensity": intensity})

    return jsonify({"error": "Invalid intensity value"}), 400


@app.route('/api/hardware/hands', methods=['POST'])
def set_hands():
    """Manually set hand positions (bypass embodied agent)"""
    data = request.get_json()
    hand = data.get('hand')  # 'left' or 'right'
    position = data.get('position', 0)

    if hand not in ['left', 'right']:
        return jsonify({"error": "Invalid hand (must be 'left' or 'right')"}), 400

    if not (0 <= position <= 100):
        return jsonify({"error": "Invalid position (must be 0-100)"}), 400

    if hand == 'left':
        assaultron.set_hardware_manual(hand_left=position)
    else:
        assaultron.set_hardware_manual(hand_right=position)

    return jsonify({"success": True, "hand": hand, "position": position})


# ============================================================================
# EMBODIED AGENT API ENDPOINTS
# ============================================================================

@app.route('/api/embodied/virtual_world')
def get_virtual_world():
    """Get complete virtual world state"""
    return jsonify(assaultron.virtual_world.to_dict())


@app.route('/api/embodied/body_state')
def get_body_state():
    """Get current virtual body state"""
    return jsonify(assaultron.virtual_world.get_body_state().to_dict())


@app.route('/api/embodied/world_state')
def get_world_state():
    """Get current world perception state"""
    return jsonify(assaultron.virtual_world.get_world_state().to_dict())


@app.route('/api/embodied/behavior_history')
def get_behavior_history():
    """Get behavior selection history"""
    history = assaultron.behavior_arbiter.get_selection_history(limit=20)
    return jsonify(history)


@app.route('/api/embodied/behaviors')
def get_available_behaviors():
    """Get list of available behaviors"""
    behaviors = describe_behavior_library()
    return jsonify({
        "behaviors": behaviors,
        "count": len(behaviors)
    })


@app.route('/api/embodied/state_history')
def get_state_history():
    """Get virtual body state transition history"""
    history = assaultron.virtual_world.get_history(limit=20)
    return jsonify(history)


@app.route('/api/embodied/world_state', methods=['POST'])
def update_world_state():
    """
    Manually update world state (for testing/simulation).

    Accepts: environment, threat_level, entities, time_of_day
    """
    data = request.get_json()

    try:
        assaultron.virtual_world.update_world(**data)
        assaultron.log_event(f"World state manually updated: {data}", "MANUAL")
        return jsonify({
            "success": True,
            "world_state": assaultron.virtual_world.get_world_state().to_dict()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ============================================================================
# VOICE SYSTEM ENDPOINTS (unchanged)
# ============================================================================

@app.route('/api/voice/start', methods=['POST'])
def start_voice_server():
    """Start xVAsynth server and load Assaultron voice model"""
    try:
        assaultron.log_event("Starting Assaultron voice system...", "VOICE")

        result = assaultron.voice_system.initialize_complete_system()

        if result["success"]:
            assaultron.voice_enabled = True
            assaultron.log_event("Assaultron voice system online", "VOICE")
            return jsonify({
                "success": True,
                "message": result["message"],
                "voice_enabled": True
            })
        else:
            assaultron.log_event(f"Voice system startup failed: {result['error']}", "ERROR")
            return jsonify({
                "success": False,
                "error": result["error"],
                "voice_enabled": False
            }), 500

    except Exception as e:
        error_msg = f"Voice system startup exception: {str(e)}"
        assaultron.log_event(error_msg, "ERROR")
        return jsonify({"success": False, "error": error_msg}), 500


@app.route('/api/voice/stop', methods=['POST'])
def stop_voice_server():
    """Stop the voice system"""
    try:
        assaultron.voice_system.shutdown()
        assaultron.voice_enabled = False
        assaultron.log_event("Voice system stopped", "VOICE")
        return jsonify({"success": True, "voice_enabled": False})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/voice/speak', methods=['POST'])
def manual_speak():
    """Manually trigger speech synthesis"""
    data = request.get_json()
    text = data.get('text', '')

    if not text:
        return jsonify({"error": "Text required"}), 400

    if not assaultron.voice_enabled:
        return jsonify({"error": "Voice system not enabled"}), 400

    assaultron.voice_system.synthesize_async(text)
    return jsonify({"success": True, "message": "Speech generation started"})


@app.route('/api/voice/status')
def voice_status():
    """Get voice system status"""
    status = assaultron.voice_system.get_status()
    status["voice_enabled"] = assaultron.voice_enabled
    return jsonify(status)


# ============================================================================
# BACKWARD COMPATIBILITY ENDPOINTS
# ============================================================================

@app.route('/api/debug/last_response')
def get_last_response():
    """Get the last AI response for debugging"""
    history = assaultron.cognitive_engine.get_conversation_history(limit=1)
    if history:
        last = history[-1]
        return jsonify({
            "raw_response": last["assistant"],
            "user_message": last["user"],
            "timestamp": last.get("timestamp")
        })
    return jsonify({"error": "No conversation history"})


@app.route('/api/tools/available')
def get_available_tools():
    """
    Legacy endpoint - tools are deprecated in embodied architecture.
    Returns behavior library instead.
    """
    return jsonify({
        "deprecated": True,
        "message": "Tool system replaced with embodied agent architecture",
        "behaviors": describe_behavior_library(),
        "info": "The AI now reasons about goals and emotions instead of using tools"
    })


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Initialize AI on startup
    threading.Thread(target=assaultron.initialize_ai, daemon=True).start()

    assaultron.log_event("Embodied Assaultron System Starting...", "SYSTEM")
    assaultron.log_event("Architecture: Cognitive → Behavioral → Motion", "SYSTEM")

    app.run(debug=True, host='127.0.0.1', port=8080)
