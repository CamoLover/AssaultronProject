"""
Assaultron Main Server - Embodied Agent Architecture

This is the refactored main server that implements the behavior-based
embodied agent system. The AI no longer uses tools to directly control
hardware - instead it reasons about goals and emotions, which are then
translated through behavioral and motion layers.
"""

from flask import Flask, render_template, request, jsonify, send_from_directory, Response
import threading
import time
import json
from datetime import datetime
import requests
from src.config import Config
import psutil
from src.voicemanager import VoiceManager
from src.stt_manager import MistralSTTManager
import logging
from logging.handlers import RotatingFileHandler
import os
from flask_httpauth import HTTPBasicAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
from queue import Queue

# Import new embodied agent layers
from src.virtual_body import (
    VirtualWorld, BodyState, WorldState, CognitiveState, BodyCommand,
    analyze_user_message_for_world_cues
)
from src.cognitive_layer import CognitiveEngine, extract_memory_from_message
from src.behavioral_layer import BehaviorArbiter, describe_behavior_library
from src.motion_controller import MotionController, HardwareStateValidator
from src.vision_system import VisionSystem
from src.notification_manager import NotificationManager

# Import autonomous agent components
from src.sandbox_manager import SandboxManager
from src.agent_logic import AgentLogic
import src.agent_ai_helpers as agent_ai_helpers

# Import monitoring service
try:
    from src.monitoring_service import get_monitoring_service
    monitoring = get_monitoring_service()
    MONITORING_ENABLED = True
except ImportError:
    MONITORING_ENABLED = False
    monitoring = None


app = Flask(__name__, template_folder='src/templates')
config = Config()


# ============================================================================
# MONITORING - Global request tracking
# ============================================================================

@app.before_request
def before_request_monitoring():
    """Track request start time for all API endpoints"""
    if MONITORING_ENABLED and request.path.startswith('/api/'):
        request._monitoring_start_time = time.time()

@app.after_request
def after_request_monitoring(response):
    """Record metrics for all API endpoints"""
    if MONITORING_ENABLED and request.path.startswith('/api/') and hasattr(request, '_monitoring_start_time'):
        duration_ms = (time.time() - request._monitoring_start_time) * 1000
        monitoring.get_collector().record_api_response(request.path, duration_ms, response.status_code)
    return response


# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# HTTP Basic Authentication
auth = HTTPBasicAuth()

# API credentials (should be in .env in production)
API_USERNAME = os.getenv("API_USERNAME", "admin")
API_PASSWORD = os.getenv("API_PASSWORD", "assaultron_dev_2026")

@auth.verify_password
def verify_password(username, password):
    """Verify API credentials"""
    if username == API_USERNAME and password == API_PASSWORD:
        return username
    return None

@auth.error_handler
def auth_error(status):
    """Return JSON error for auth failures"""
    return jsonify({"error": "Unauthorized access"}), status

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging():
    """Configure application-wide logging with rotation and proper formatting"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with colored output-like formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    # File handler with rotation (10MB max, keep 5 backups)
    os.makedirs('debug/logs', exist_ok=True)
    file_handler = RotatingFileHandler(
        'debug/logs/assaultron.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Error file handler (errors only)
    error_handler = RotatingFileHandler(
        'debug/logs/assaultron_errors.log',
        maxBytes=10*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    return logger

# Initialize logging
app_logger = setup_logging()
logger = logging.getLogger('assaultron.main')


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

        # Update monitoring
        if MONITORING_ENABLED:
            monitoring.get_collector().update_system_status(ai_active=False)

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
        self.ai_active = True
        self.log_event("Cognitive Engine initialized", "SYSTEM")

        # Update monitoring
        if MONITORING_ENABLED:
            monitoring.get_collector().update_system_status(ai_active=True)

        # Behavioral Layer (behavior selection)
        self.behavior_arbiter = BehaviorArbiter()
        self.log_event(f"Behavior Arbiter initialized with {len(self.behavior_arbiter.behaviors)} behaviors", "SYSTEM")

        # Motion Controller (hardware translation)
        self.motion_controller = MotionController()
        self.log_event("Motion Controller initialized", "SYSTEM")

        # Voice system
        self.voice_system = VoiceManager(logger=self)
        self.voice_enabled = False
        self.voice_event_queues = []  # SSE clients listening for audio ready events

        # Update monitoring
        if MONITORING_ENABLED:
            monitoring.get_collector().update_system_status(voice_enabled=False)

        # Register callback for real-time audio notifications
        self.voice_system.set_audio_ready_callback(self._broadcast_audio_ready)
        self.log_event("Voice Manager initialized", "SYSTEM")

        # Speech-to-Text system
        mistral_key = os.getenv("MISTRAL_KEY", "")
        self.stt_manager = None
        self.stt_event_queues = []  # SSE clients listening for STT events
        if mistral_key:
            try:
                sample_rate = int(os.getenv("STT_SAMPLE_RATE", "16000"))
                chunk_duration = int(os.getenv("STT_CHUNK_DURATION_MS", "480"))
                self.stt_manager = MistralSTTManager(
                    api_key=mistral_key,
                    sample_rate=sample_rate,
                    chunk_duration_ms=chunk_duration
                )
                self.log_event("STT Manager initialized (Mistral Voxtral)", "SYSTEM")
            except Exception as e:
                self.log_event(f"Failed to initialize STT Manager: {e}", "ERROR")
                self.stt_manager = None
        else:
            self.log_event("STT Manager not initialized (MISTRAL_KEY not set)", "WARN")

        # Vision system (Perception Layer)
        self.vision_system = VisionSystem(logger=self)
        self.vision_system.enumerate_cameras()  # Discover available cameras
        self.log_event("Vision System initialized", "SYSTEM")

        # Notification system (pass cognitive_engine for smart questions)
        self.notification_manager = NotificationManager(
            app_name="Assaultron AI",
            cognitive_engine=self.cognitive_engine
        )
        self.notification_manager.configure(
            min_interval=30,  # 30 seconds between notifications
            inactivity_threshold_min=300,  # 5 minutes minimum
            inactivity_threshold_max=1800  # 30 minutes maximum
        )
        self.notification_manager.start_inactivity_monitoring(check_interval=60)
        self.log_event("Notification Manager initialized (AI-powered check-ins: 5-30min)", "SYSTEM")

        # Background monitoring for proactive notifications
        self.background_monitoring_enabled = False
        self.background_thread = None
        
        # Autonomous Agent System
        sandbox_path = os.getenv("SANDBOX_PATH", "./src/sandbox")
        self.sandbox_manager = SandboxManager(sandbox_path)
        self.agent_logic = AgentLogic(self.cognitive_engine, self.sandbox_manager)
        self.agent_tasks = {}  # Track running agent tasks
        self.log_event(f"Autonomous Agent initialized with sandbox: {sandbox_path}", "SYSTEM")

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

        # Use proper logging instead of print
        log_level = getattr(logging, event_type, logging.INFO)
        logger = logging.getLogger(f'assaultron.{event_type.lower()}')
        logger.log(log_level, message)

    def _broadcast_audio_ready(self, filename):
        """Broadcast audio ready event to all connected SSE clients"""
        audio_url = f"/api/voice/audio/{filename}"
        message = {
            "type": "audio_ready",
            "url": audio_url,
            "filename": filename
        }

        # Determine message source (default to web if not set)
        source = getattr(self, 'last_message_source', 'web')

        # Send to all connected clients
        # Note: We broadcast to all clients regardless of source
        # The Discord bot and web UI will handle playing/not playing based on their own state
        dead_queues = []
        for queue in self.voice_event_queues:
            try:
                queue.put_nowait(message)
            except:
                dead_queues.append(queue)

        # Clean up disconnected clients
        for queue in dead_queues:
            if queue in self.voice_event_queues:
                self.voice_event_queues.remove(queue)

        # Reset source after broadcast
        self.last_message_source = 'web'

    def _broadcast_voice_notification(self, text):
        """Broadcast voice activation notification to all connected SSE clients"""
        message = {
            "type": "voice_notification"
        }

        # Send to all connected clients
        dead_queues = []
        for queue in self.voice_event_queues:
            try:
                queue.put_nowait(message)
            except:
                dead_queues.append(queue)

        # Clean up disconnected clients
        for queue in dead_queues:
            if queue in self.voice_event_queues:
                self.voice_event_queues.remove(queue)

    def _broadcast_agent_completion(self, message_text):
        """Broadcast agent completion message to all connected SSE clients"""
        message = {
            "type": "agent_completion",
            "message": message_text,
            "timestamp": datetime.now().isoformat()
        }

        # Send to all connected clients
        dead_queues = []
        for queue in self.voice_event_queues:
            try:
                queue.put_nowait(message)
            except:
                dead_queues.append(queue)

        # Clean up disconnected clients
        for queue in dead_queues:
            if queue in self.voice_event_queues:
                self.voice_event_queues.remove(queue)

        self.log_event(f"Broadcasted agent completion: {message_text[:50]}...", "AGENT")

    def process_message(self, user_message: str, image_path: str = None) -> dict:
        """
        Process user message through the embodied agent pipeline.

        Pipeline:
        1. Update world state based on user message cues
        2. Cognitive Layer: LLM generates CognitiveState
        3. Behavioral Layer: Select and execute behavior
        4. Motion Controller: Translate to hardware
        5. Update virtual body
        6. Voice synthesis (if enabled)

        Args:
            user_message: The user's text message
            image_path: Optional path to an attached image file

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

            # Step 1a: Update mood based on interaction
            is_question = "?" in user_message
            self.virtual_world.update_mood(
                user_message=user_message,
                is_question=is_question,
                message_length=len(user_message)
            )
            mood_state = self.virtual_world.get_mood_state()
            self.log_event(
                f"Mood: curiosity={mood_state.curiosity:.2f}, irritation={mood_state.irritation:.2f}, "
                f"boredom={mood_state.boredom:.2f}, attachment={mood_state.attachment:.2f}",
                "MOOD"
            )

            # Step 1c: Detect if this is an actionable task for the agent
            task_detected, task_description = self._detect_agent_task(user_message)
            agent_context = ""
            
            if task_detected:
                self.log_event(f"Task detected: {task_description}", "AGENT")
                
                # Generate immediate acknowledgment from AI
                acknowledgment = agent_ai_helpers.generate_task_acknowledgment(
                    self.cognitive_engine,
                    task_description,
                    mood_state
                )
                
                # Enhance task with personality
                enhanced_task = agent_ai_helpers.enhance_task_with_personality(task_description)
                
                # Start agent in background
                task_id = f"task_{int(time.time())}_{len(self.agent_tasks)}"
                
                # Get conversation context for the agent
                recent_history = self.cognitive_engine.conversation_history[-10:]
                formatted_history = []
                for exchange in recent_history:
                    formatted_history.append(f"User: {exchange['user']}")
                    formatted_history.append(f"AI: {exchange['assistant']}")
                history_context = "\n".join(formatted_history)

                agent_ai_helpers.run_agent_in_background(
                    agent_logic=self.agent_logic,
                    agent_tasks=self.agent_tasks,
                    task_id=task_id,
                    enhanced_task=enhanced_task,
                    original_task=task_description,
                    cognitive_engine=self.cognitive_engine,
                    voice_system=self.voice_system,
                    voice_enabled=self.voice_enabled,
                    log_callback=self.log_event,
                    broadcast_callback=self._broadcast_agent_completion,
                    user_message=user_message,
                    conversation_history=history_context
                )
                
                # Queue voice message for acknowledgment if enabled
                if self.voice_enabled:
                    self.voice_system.synthesize_async(acknowledgment)
                # Manually save to history (since helper doesn't)
                try:
                    self.cognitive_engine._update_history(user_message, acknowledgment)
                except Exception as e:
                    self.log_event(f"Error updating history: {e}", "ERROR")

                return {
                    "success": True,
                    "dialogue": acknowledgment,
                    "timestamp": datetime.now().isoformat(),
                    "cognitive_state": {"emotion": mood_state.dominant_emotion, "thought": "Starting autonomous task"},
                    "hardware_state": self.get_hardware_state(),
                    "body_state": {"posture": "alert", "gesture": "nod"},
                    "mood": mood_state.__dict__,
                    "metadata": {
                        "task_started": True,
                        "task_id": task_id
                    }
                }

            # Step 1b: Integrate vision data into world state
            vision_context = ""
            vision_image_b64 = None
            if self.vision_system.state.enabled:
                vision_entities = self.vision_system.get_entities_for_world_state()
                vision_data = self.vision_system.get_scene_for_cognitive_layer()

                # Get raw frame for AI vision (without detection overlay)
                vision_image_b64 = self.vision_system.get_raw_frame_b64()

                # Update world state with vision data
                if vision_entities:
                    self.virtual_world.update_world(entities=vision_entities)
                    world_state = self.virtual_world.get_world_state()  # Refresh

                # Update threat level from vision
                if vision_data.get("threat_level", "none") != "none":
                    self.virtual_world.update_world(threat_level=vision_data["threat_level"])
                    world_state = self.virtual_world.get_world_state()  # Refresh
                    self.log_event(f"Vision threat assessment: {vision_data['threat_level']}", "VISION")

                # Build vision context for cognitive layer
                vision_context = vision_data.get("scene_description", "")
                if vision_data.get("entities"):
                    entity_details = [f"{e['class_name']} ({e['confidence']:.0%} confidence)"
                                      for e in vision_data["entities"][:5]]
                    if entity_details:
                        vision_context += f" | Details: {', '.join(entity_details)}"

                logging.getLogger('assaultron.vision').debug(f"VISION CONTEXT SENT TO AI: '{vision_context}'")
                self.log_event(f"Vision: {vision_data['scene_description']}", "VISION")

            # Step 2: Cognitive Layer - Generate intent
            provider_label = Config.LLM_PROVIDER.upper()
            self.log_event(f"Cognitive: Processing with {provider_label}...", "COGNITIVE")
            memory_summary = self.cognitive_engine.get_memory_summary()

            # Track LLM timing
            llm_start = time.time()

            cognitive_state = self.cognitive_engine.process_input(
                user_message=user_message,
                world_state=world_state,
                body_state=body_state,
                mood_state=mood_state,
                memory_summary=memory_summary,
                vision_context=vision_context,
                agent_context=agent_context,
                vision_image_b64=vision_image_b64,
                attachment_image_path=image_path
            )

            # Record LLM metrics
            llm_duration = (time.time() - llm_start) * 1000
            if MONITORING_ENABLED:
                # Rough estimate for tokens (will be more accurate with actual token count)
                prompt_tokens = len(user_message.split()) * 2
                response_tokens = len(cognitive_state.dialogue.split()) * 2
                monitoring.get_collector().record_llm_request(
                    model=provider_label,
                    prompt_tokens=prompt_tokens,
                    response_tokens=response_tokens,
                    duration_ms=llm_duration
                )
                monitoring.get_collector().record_system_delay('cognitive_layer', llm_duration)

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

            # Step 6: Memory extraction is now handled automatically by cognitive_state.memory
            # The AI decides what to remember and reformulates it naturally (see cognitive_layer.py:223-224)

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

            # Step 7: Check for notification triggers
            self._check_and_send_notifications(cognitive_state, world_state)

            # Step 8: Voice synthesis (if enabled)
            # Note: Voice timing is tracked inside VoiceManager.synthesize_voice()
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
            logging.getLogger('assaultron.error').exception("Exception during message processing:")

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
    
    def _detect_agent_task(self, message: str) -> tuple:
        """
        Detect if the user message is a task for the autonomous agent using LLM.
        
        Args:
            message: User message
            
        Returns:
            Tuple (is_task, task_description)
        """
        # Check if user explicitly wants to bypass agent invocation
        message_lower_check = message.lower()
        no_agent_phrases = [
            "don't use agent", "dont use agent",
            "don't call agent", "dont call agent",
            "don't use the agent", "dont use the agent",
            "don't call the agent", "dont call the agent",
            "don't start agent", "dont start agent",
            "don't start the agent", "dont start the agent",
            "don't run agent", "dont run agent",
            "don't run the agent", "dont run the agent",
            "don't trigger agent", "dont trigger agent",
            "don't trigger the agent", "dont trigger the agent",
            "no agent", "without agent", "skip agent",
            "not for agent", "not for the agent",
        ]
        if any(phrase in message_lower_check for phrase in no_agent_phrases):
            return False, ""

        # Quick check for obvious non-tasks to save LLM calls
        if len(message.split()) < 2:
            return False, ""
            
        # Use LLM to classify intent
        prompt = f"""Analyze the following user message and determine if it is a request for the autonomous agent to perform a specific task (like creating files, writing code, researching, etc.) or just a conversational statement/question.

User Message: "{message}"

Rules:
1. "Create a website", "Write a poem", "Research python" -> ACTIVE_TASK
2. "I need to fix this", "I want to learn python", "How are you?" -> CONVERSATIONAL
3. "Fix the footer", "Update the file" -> ACTIVE_TASK (if it implies YOU should do it)
4. "I will fix it", "I am coding" -> CONVERSATIONAL

Respond with JSON only:
{{
    "is_task": true/false,
    "task_description": "extracted task if true, else empty string",
    "reasoning": "brief explanation"
}}"""

        try:
            # We use a direct LLM call here for speed and specific formatting
            # This bypasses the full cognitive layer processing
            response = self.cognitive_engine._call_llm([
                {"role": "system", "content": "You are an intent classifier. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ])
            
            import json
            import re
            
            # extract JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return result.get("is_task", False), result.get("task_description", "")
            
        except Exception as e:
            self.log_event(f"Intent detection failed: {e}. Falling back to keyword search.", "ERROR")
            
        # Fallback to keyword matching if LLM fails
        message_lower = message.lower()
        
        action_verbs = [
            'create', 'make', 'build', 'write', 'generate', 'develop',
            'code', 'program', 'design', 'implement', 'construct',
            'research', 'find', 'search', 'look up', 'investigate',
            'analyze', 'test', 'run', 'execute', 'deploy'
        ]
        
        creation_indicators = [
            'website', 'web page', 'html', 'css', 'javascript', 'php',
            'file', 'folder', 'directory', 'script', 'program',
            'app', 'application', 'project', 'code', 'document',
            'poem', 'story', 'article', 'report', 'summary'
        ]
        
        has_action = any(verb in message_lower for verb in action_verbs)
        has_creation = any(indicator in message_lower for indicator in creation_indicators)
        
        if has_action and has_creation:
            # Extract task description (remove greetings)
            task = message
            greetings = ['hello', 'hi', 'hey', 'greetings']
            for greeting in greetings:
                # Remove greeting at start of message
                if task.lower().startswith(greeting):
                    task = task[len(greeting):].strip(' ,')
            
            return True, task
        
        return False, ""

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

    def _check_and_send_notifications(self, cognitive_state: CognitiveState, world_state: WorldState):
        """
        Check if notifications should be sent based on cognitive state and world state.

        IMPORTANT: This function is called during active conversation (when user is talking).
        Notifications should NOT be sent during active chat - user already has full attention on AI.

        This function only updates activity timestamp to prevent inactivity check-ins.

        Real notifications should only come from:
        - Background monitoring thread (not implemented yet)
        - Vision system detecting threats when idle (not implemented yet)
        """
        # Update user activity timestamp to prevent check-in notifications
        self.notification_manager.update_user_activity()

        # NOTE: We intentionally DO NOT send notifications here because:
        # - User is actively talking to the AI (already paying attention)
        # - Notifications during conversation would be redundant and annoying
        # - The response is already being displayed in the chat interface

        # Future: Background monitoring thread will check these conditions when user is NOT talking

    def start_background_monitoring(self, check_interval: int = 30):
        """
        Start background monitoring thread that checks for issues when user is NOT actively talking.

        This thread will:
        - Monitor vision system for threats (only when vision is enabled)
        - Check system health
        - Send notifications only when user is IDLE (not in active conversation)

        Args:
            check_interval: How often to check (seconds)
        """
        if self.background_thread and self.background_thread.is_alive():
            return  # Already running

        self.background_monitoring_enabled = True

        def monitoring_loop():
            while self.background_monitoring_enabled:
                time.sleep(check_interval)

                if not self.background_monitoring_enabled:
                    break

                # Check if user has been inactive (not talking)
                time_since_activity = (datetime.now() - self.notification_manager.last_user_interaction).total_seconds()

                # Only check for issues if user hasn't talked in at least 60 seconds
                # (This means they're not actively in conversation)
                if time_since_activity < 60:
                    continue  # User is actively chatting, skip monitoring

                # Check vision system for threats (only if enabled)
                if self.vision_system.state.enabled:
                    world_state = self.virtual_world.get_world_state()
                    threat_level = world_state.threat_level

                    # Send notification for medium/high threats
                    if threat_level in ["medium", "high"]:
                        entity_count = len(world_state.entities)
                        self.notification_manager.notify_threat_detected(
                            threat_level=threat_level,
                            entity_count=entity_count
                        )
                        self.log_event(f"Background: Threat detected ({threat_level})", "SYSTEM")

        self.background_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.background_thread.start()
        self.log_event("Background monitoring started", "SYSTEM")

    def stop_background_monitoring(self):
        """Stop the background monitoring thread"""
        self.background_monitoring_enabled = False
        self.log_event("Background monitoring stopped", "SYSTEM")


# ============================================================================
# CONVERSATION LOGGING HELPER
# ============================================================================
# Conversation logging disabled - logs are only kept in main assaultron.log


# ============================================================================
# FLASK APPLICATION
# ============================================================================

# Initialize Embodied Assaultron
assaultron = EmbodiedAssaultronCore()


@app.route('/')
def index():
    return render_template('index.html')


# ============================================================================
# HEALTH CHECK & METRICS ENDPOINTS
# ============================================================================

@app.route('/health')
@app.route('/api/health')
def health_check():
    """
    Health check endpoint for monitoring systems.
    Returns system health status and metrics.
    """
    try:
        # Check AI connectivity
        ai_status = "healthy" if assaultron.ai_active else "unhealthy"

        # Check vision system
        vision_status = "enabled" if assaultron.vision_system.state.enabled else "disabled"

        # Check voice system
        voice_status = "enabled" if assaultron.voice_enabled else "disabled"

        # System metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('.')

        # Uptime
        uptime_seconds = (datetime.now() - assaultron.start_time).total_seconds()

        # Overall health determination
        overall_status = "healthy"
        issues = []

        if not assaultron.ai_active:
            overall_status = "degraded"
            issues.append("AI connection unavailable")

        if cpu_percent > 90:
            overall_status = "degraded"
            issues.append(f"High CPU usage: {cpu_percent}%")

        if memory.percent > 90:
            overall_status = "degraded"
            issues.append(f"High memory usage: {memory.percent}%")

        if disk.percent > 90:
            overall_status = "degraded"
            issues.append(f"Low disk space: {disk.percent}% used")

        return jsonify({
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": int(uptime_seconds),
            "checks": {
                "ai_engine": ai_status,
                "vision_system": vision_status,
                "voice_system": voice_status
            },
            "metrics": {
                "cpu_percent": round(cpu_percent, 2),
                "memory_percent": round(memory.percent, 2),
                "memory_available_mb": round(memory.available / 1024 / 1024, 2),
                "disk_percent": round(disk.percent, 2),
                "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "total_requests": assaultron.performance_stats["total_requests"],
                "avg_response_time_ms": assaultron.performance_stats["avg_response_time"],
                "last_response_time_ms": assaultron.performance_stats["last_response_time"]
            },
            "issues": issues,
            "version": "2.0-embodied"
        }), 200 if overall_status == "healthy" else 503

    except Exception as e:
        logger.exception("Health check failed")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/api/metrics')
def metrics():
    """
    Prometheus-compatible metrics endpoint.
    Returns metrics in plain text format.
    """
    try:
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        uptime_seconds = (datetime.now() - assaultron.start_time).total_seconds()

        metrics_text = f"""# HELP assaultron_uptime_seconds Total uptime in seconds
# TYPE assaultron_uptime_seconds counter
assaultron_uptime_seconds {int(uptime_seconds)}

# HELP assaultron_requests_total Total number of chat requests processed
# TYPE assaultron_requests_total counter
assaultron_requests_total {assaultron.performance_stats["total_requests"]}

# HELP assaultron_response_time_ms Average response time in milliseconds
# TYPE assaultron_response_time_ms gauge
assaultron_response_time_ms {assaultron.performance_stats["avg_response_time"]}

# HELP assaultron_cpu_percent CPU usage percentage
# TYPE assaultron_cpu_percent gauge
assaultron_cpu_percent {cpu_percent}

# HELP assaultron_memory_percent Memory usage percentage
# TYPE assaultron_memory_percent gauge
assaultron_memory_percent {memory.percent}

# HELP assaultron_ai_active AI engine status (1=active, 0=inactive)
# TYPE assaultron_ai_active gauge
assaultron_ai_active {1 if assaultron.ai_active else 0}

# HELP assaultron_vision_active Vision system status (1=active, 0=inactive)
# TYPE assaultron_vision_active gauge
assaultron_vision_active {1 if assaultron.vision_system.state.enabled else 0}

# HELP assaultron_voice_active Voice system status (1=active, 0=inactive)
# TYPE assaultron_voice_active gauge
assaultron_voice_active {1 if assaultron.voice_enabled else 0}
"""
        return metrics_text, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    except Exception as e:
        logger.exception("Metrics generation failed")
        return f"# ERROR: {str(e)}", 500, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/api/chat/upload_image', methods=['POST'])
@limiter.limit("20 per minute")  # Rate limit for image uploads
def upload_chat_image():
    """
    Upload an image to attach to a chat message.
    Returns the path to the saved image.
    """
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

    if file_ext not in allowed_extensions:
        return jsonify({"error": f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"}), 400

    # Create chat_images directory if it doesn't exist
    import os
    os.makedirs('ai-data/chat_images', exist_ok=True)

    # Generate unique filename
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"chat_{timestamp}.{file_ext}"
    filepath = os.path.join('ai-data/chat_images', filename)

    # Save file
    try:
        file.save(filepath)
        return jsonify({
            "success": True,
            "image_path": filepath,
            "filename": filename
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to save image: {str(e)}"}), 500


@app.route('/chat_images/<path:filename>')
def serve_chat_image(filename):
    """Serve uploaded chat images"""
    return send_from_directory('ai-data/chat_images', filename)


@app.route('/api/chat', methods=['POST'])
@limiter.limit("100 per minute")  # Rate limit: 100 messages per minute (reasonable for active conversation)
def chat():
    """
    Main chat endpoint - processes user message through embodied agent pipeline.
    Rate limited to 100 requests per minute to prevent abuse while allowing natural conversation.
    """
    data = request.get_json()
    message = data.get('message', '').strip()
    image_path = data.get('image_path', None)  # Optional image attachment
    source = data.get('source', 'web')  # Track message source (web, discord, etc.)

    if not message:
        return jsonify({"error": "Empty message"}), 400

    # Input validation
    if len(message) > 5000:
        return jsonify({"error": "Message too long (max 5000 characters)"}), 400

    # Log received input
    if image_path:
        assaultron.log_event(f"INPUT RECEIVED: '{message}' (with image: {image_path})", "CHAT")
    else:
        assaultron.log_event(f"INPUT RECEIVED: '{message}'", "CHAT")

    # Store message source for voice system
    assaultron.last_message_source = source

    # Auto-detect Discord bot activity
    if MONITORING_ENABLED and source == 'discord':
        monitoring.get_collector().update_system_status(discord_bot_active=True)

    # Track message pipeline start
    pipeline_start = time.time()

    # Process through embodied agent pipeline
    result = assaultron.process_message(message, image_path=image_path)

    # Calculate timing
    pipeline_duration = (time.time() - pipeline_start) * 1000

    # Record monitoring metrics
    if MONITORING_ENABLED:
        monitoring.get_collector().record_message_pipeline('full_pipeline', pipeline_duration)

    if result["success"]:
        # Return response in format compatible with existing web UI
        return jsonify({
            "response": result["dialogue"],
            "timestamp": result["timestamp"],
            "cognitive_state": result.get("cognitive_state"),
            "hardware_state": result.get("hardware_state"),
            "body_state": result.get("body_state"),
            "provider": Config.LLM_PROVIDER,
            "model": Config.OPENROUTER_MODEL if Config.LLM_PROVIDER == "openrouter" else (Config.GEMINI_MODEL if Config.LLM_PROVIDER == "gemini" else Config.AI_MODEL),
            "voice_enabled": assaultron.voice_enabled
        })
    else:
        # Record error
        if MONITORING_ENABLED:
            monitoring.get_collector().record_error('chat_error', 'api', result.get("error", "Unknown error"))

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

    current_model = Config.OPENROUTER_MODEL if Config.LLM_PROVIDER == "openrouter" else (Config.GEMINI_MODEL if Config.LLM_PROVIDER == "gemini" else Config.AI_MODEL)

    return jsonify({
        "status": assaultron.status,
        "ai_active": assaultron.ai_active,
        "provider": Config.LLM_PROVIDER,
        "model": current_model,
        "conversation_count": len(assaultron.cognitive_engine.conversation_history),
        "uptime_seconds": int(uptime_seconds),
        "performance": assaultron.performance_stats,
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent
        },
        "architecture": "embodied_agent"
    })


@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    """Clear conversation history"""
    assaultron.cognitive_engine.clear_history()
    assaultron.log_event("Conversation history cleared", "SYSTEM")
    return jsonify({"success": True})


@app.route('/api/history')
def get_history():
    """Get conversation history"""
    history = assaultron.cognitive_engine.get_conversation_history(limit=50) # Return more for restoration
    return jsonify(history)


@app.route('/api/hardware')
def get_hardware():
    """Get current hardware state (backward compatible)"""
    return jsonify(assaultron.get_hardware_state())


@app.route('/api/memory')
def get_memory():
    """Get AI memory context (short-term)"""
    memories = assaultron.cognitive_engine.memory_context[-20:]
    return jsonify(memories)


@app.route('/api/embodied/long_term_memories')
def get_long_term_memories():
    """Get AI core memories"""
    return jsonify(assaultron.cognitive_engine.memory_context)


@app.route('/api/embodied/long_term_memories/delete', methods=['POST'])
def delete_long_term_memory():
    """Remove a core memory by index"""
    data = request.get_json()
    index = data.get('index')
    
    if index is not None and 0 <= index < len(assaultron.cognitive_engine.memory_context):
        content = assaultron.cognitive_engine.memory_context.pop(index)["content"]
        assaultron.cognitive_engine._save_memories()
        assaultron.log_event(f"Core memory deleted: {content}", "MEMORY")
        return jsonify({"success": True})
    
    return jsonify({"error": "Invalid index"}), 400


@app.route('/api/embodied/long_term_memories/add', methods=['POST'])
def add_long_term_memory():
    """Manually add a core memory"""
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({"error": "Content required"}), 400
        
    if len(assaultron.cognitive_engine.memory_context) >= 50:
        return jsonify({"error": "Memory limit reached (max 50)"}), 400
        
    assaultron.cognitive_engine.memory_context.append({
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    assaultron.cognitive_engine._save_memories()
    assaultron.log_event(f"Core memory manually added: {content}", "MEMORY")
    return jsonify({"success": True})


@app.route('/api/embodied/long_term_memories/edit', methods=['POST'])
def edit_long_term_memory():
    """Edit an existing core memory"""
    data = request.get_json()
    index = data.get('index')
    content = data.get('content', '').strip()
    
    if index is not None and 0 <= index < len(assaultron.cognitive_engine.memory_context) and content:
        old_content = assaultron.cognitive_engine.memory_context[index]["content"]
        assaultron.cognitive_engine.memory_context[index]["content"] = content
        assaultron.cognitive_engine._save_memories()
        assaultron.log_event(f"Core memory edited: {old_content} -> {content}", "MEMORY")
        return jsonify({"success": True})
    
    return jsonify({"error": "Invalid parameters"}), 400


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


@app.route('/api/embodied/mood_state')
def get_mood_state():
    """Get current internal mood state (read-only)"""
    return jsonify(assaultron.virtual_world.get_mood_state().to_dict())


@app.route('/api/embodied/mood_history')
def get_mood_history():
    """Get mood state history over time"""
    history = assaultron.virtual_world.get_mood_history(limit=50)
    return jsonify(history)


@app.route('/api/embodied/mood_state', methods=['POST'])
def update_mood_state():
    """
    Manually update mood state parameters (for UI control).

    Accepts: curiosity, irritation, boredom, attachment (0.0-1.0)
    """
    data = request.get_json()

    try:
        assaultron.virtual_world.set_mood_manually(**data)
        assaultron.log_event(f"Mood state manually updated: {data}", "MANUAL")
        return jsonify({
            "success": True,
            "mood_state": assaultron.virtual_world.get_mood_state().to_dict()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ============================================================================
# NOTIFICATION SYSTEM ENDPOINTS
# ============================================================================

@app.route('/api/notifications/test', methods=['POST'])
def test_notification():
    """Send a test notification"""
    data = request.get_json()
    title = data.get('title', 'Assaultron AI - Test')
    message = data.get('message', 'Discord notification system is working!')

    success = assaultron.notification_manager.send_notification(
        title=title,
        message=message,
        color=0x3498db,  # Blue
        force=True
    )

    return jsonify({
        "success": success,
        "message": "Discord notification sent! Check your channel." if success else "Failed to send notification"
    })


@app.route('/api/notifications/request_attention', methods=['POST'])
def request_attention():
    """Manually trigger an attention request notification"""
    data = request.get_json()
    reason = data.get('reason', 'The AI wants your attention')
    dialogue = data.get('dialogue')

    assaultron.notification_manager.notify_attention_request(
        reason=reason,
        dialogue=dialogue
    )
    assaultron.log_event(f"Manual attention request: {reason}", "SYSTEM")

    return jsonify({
        "success": True,
        "message": "Attention notification sent"
    })


@app.route('/api/notifications/config', methods=['GET', 'POST'])
def notification_config():
    """Get or update notification configuration"""
    if request.method == 'GET':
        last_notif_time = assaultron.notification_manager.last_notification_sent_time
        time_since_last_notif = None
        if last_notif_time:
            time_since_last_notif = (datetime.now() - last_notif_time).total_seconds()

        return jsonify({
            "min_interval": assaultron.notification_manager.min_notification_interval,
            "inactivity_threshold_min": assaultron.notification_manager.inactivity_threshold_min,
            "inactivity_threshold_max": assaultron.notification_manager.inactivity_threshold_max,
            "inactivity_monitoring": assaultron.notification_manager.inactivity_check_enabled,
            "waiting_for_response": assaultron.notification_manager.waiting_for_response,
            "notification_timeout": assaultron.notification_manager.notification_timeout,
            "time_since_last_notification": time_since_last_notif
        })
    else:
        data = request.get_json()
        min_interval = data.get('min_interval')
        inactivity_threshold_min = data.get('inactivity_threshold_min')
        inactivity_threshold_max = data.get('inactivity_threshold_max')

        assaultron.notification_manager.configure(
            min_interval=min_interval,
            inactivity_threshold_min=inactivity_threshold_min,
            inactivity_threshold_max=inactivity_threshold_max
        )

        return jsonify({
            "success": True,
            "message": "Notification settings updated"
        })


@app.route('/api/notifications/inactivity/toggle', methods=['POST'])
def toggle_inactivity_monitoring():
    """Start or stop inactivity monitoring"""
    data = request.get_json()
    enable = data.get('enable', True)

    if enable:
        assaultron.notification_manager.start_inactivity_monitoring()
        message = "Inactivity monitoring started"
    else:
        assaultron.notification_manager.stop_inactivity_monitoring()
        message = "Inactivity monitoring stopped"

    assaultron.log_event(message, "SYSTEM")

    return jsonify({
        "success": True,
        "message": message,
        "enabled": enable,
        "waiting_for_response": assaultron.notification_manager.waiting_for_response
    })


@app.route('/api/notifications/reset_waiting', methods=['POST'])
def reset_waiting_flag():
    """Manually reset the waiting_for_response flag (for debugging/recovery)"""
    old_value = assaultron.notification_manager.waiting_for_response
    assaultron.notification_manager.waiting_for_response = False
    assaultron.log_event(f"Manually reset waiting_for_response flag (was: {old_value})", "SYSTEM")

    return jsonify({
        "success": True,
        "message": f"Reset waiting flag from {old_value} to False",
        "old_value": old_value,
        "new_value": False
    })


@app.route('/api/notifications/background/toggle', methods=['POST'])
def toggle_background_monitoring():
    """Start or stop background threat monitoring (vision system)"""
    data = request.get_json()
    enable = data.get('enable', True)

    if enable:
        check_interval = data.get('check_interval', 30)
        assaultron.start_background_monitoring(check_interval=check_interval)
        message = f"Background monitoring started (checks every {check_interval}s)"
    else:
        assaultron.stop_background_monitoring()
        message = "Background monitoring stopped"

    return jsonify({
        "success": True,
        "message": message,
        "enabled": enable
    })


@app.route('/api/notifications/user_active', methods=['POST'])
@limiter.exempt  # Exempt from rate limiting - this is a heartbeat endpoint
def mark_user_active():
    """
    Endpoint for frontend to call when user is actively using the chat.
    This prevents notifications from being sent while user is engaged.

    Frontend should call this when:
    - User focuses the chat input
    - User scrolls through messages
    - User sends a message (already handled)
    - User is viewing the chat window

    IMPORTANT: This endpoint is exempt from rate limiting because it's a
    critical heartbeat mechanism that prevents false inactivity notifications.
    """
    assaultron.notification_manager.update_user_activity()
    return jsonify({"success": True})


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

            # Update monitoring
            if MONITORING_ENABLED:
                monitoring.get_collector().update_system_status(voice_enabled=True)
            # Send notification that voice is activated
            assaultron._broadcast_voice_notification("Voice system activated")
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

        # Update monitoring
        if MONITORING_ENABLED:
            monitoring.get_collector().update_system_status(voice_enabled=False)

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
@limiter.exempt  # Exempt from rate limiting - polled frequently for audio playback
def voice_status():
    """Get voice system status - polled frequently to detect new audio"""
    status = assaultron.voice_system.get_status()
    status["voice_enabled"] = assaultron.voice_enabled
    return jsonify(status)


@app.route('/api/voice/audio/<filename>')
def serve_audio(filename):
    """Serve generated audio files to the frontend"""
    try:
        audio_dir = assaultron.voice_system.audio_output_dir
        return send_from_directory(audio_dir, filename, mimetype='audio/wav')
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route('/api/voice/events')
@limiter.exempt
def voice_events():
    """Server-Sent Events stream for real-time voice notifications"""
    def event_stream():
        # Create a queue for this client
        client_queue = Queue()

        # Add queue to broadcast list
        if not hasattr(assaultron, 'voice_event_queues'):
            assaultron.voice_event_queues = []
        assaultron.voice_event_queues.append(client_queue)

        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"

            # Listen for events
            while True:
                try:
                    # Wait for events with timeout to send keepalive
                    message = client_queue.get(timeout=30)
                    yield f"data: {json.dumps(message)}\n\n"
                except:
                    # Send keepalive comment every 30 seconds
                    yield ": keepalive\n\n"
        except GeneratorExit:
            # Client disconnected
            if client_queue in assaultron.voice_event_queues:
                assaultron.voice_event_queues.remove(client_queue)

    return Response(event_stream(), mimetype='text/event-stream')


# ============================================================================
# SPEECH-TO-TEXT ENDPOINTS
# ============================================================================

@app.route('/api/stt/start', methods=['POST'])
def start_stt():
    """Start speech-to-text transcription"""
    try:
        if not assaultron.stt_manager:
            return jsonify({
                "success": False,
                "error": "STT not available (MISTRAL_KEY not configured or dependencies missing)"
            }), 503

        success = assaultron.stt_manager.start_listening()

        if success:
            assaultron.log_event("STT started listening", "STT")
            return jsonify({
                "success": True,
                "status": "listening"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to start STT"
            }), 500

    except Exception as e:
        error_msg = f"STT startup exception: {str(e)}"
        assaultron.log_event(error_msg, "ERROR")
        return jsonify({"success": False, "error": error_msg}), 500


@app.route('/api/stt/stop', methods=['POST'])
def stop_stt():
    """Stop speech-to-text transcription"""
    try:
        if not assaultron.stt_manager:
            return jsonify({"success": False, "error": "STT not available"}), 503

        success = assaultron.stt_manager.stop_listening()

        if success:
            assaultron.log_event("STT stopped listening", "STT")
            return jsonify({
                "success": True,
                "status": "stopped"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to stop STT"
            }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/stt/pause', methods=['POST'])
def pause_stt():
    """Temporarily pause STT (e.g., during AI speech)"""
    try:
        if not assaultron.stt_manager:
            return jsonify({"success": False, "error": "STT not available"}), 503

        success = assaultron.stt_manager.pause_listening()

        if success:
            assaultron.log_event("STT paused", "STT")
            return jsonify({
                "success": True,
                "status": "paused"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to pause STT"
            }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/stt/resume', methods=['POST'])
def resume_stt():
    """Resume STT after pause"""
    try:
        if not assaultron.stt_manager:
            return jsonify({"success": False, "error": "STT not available"}), 503

        success = assaultron.stt_manager.resume_listening()

        if success:
            assaultron.log_event("STT resumed", "STT")
            return jsonify({
                "success": True,
                "status": "listening"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to resume STT"
            }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/stt/status')
@limiter.exempt  # Exempt from rate limiting
def stt_status():
    """Get STT status"""
    try:
        if not assaultron.stt_manager:
            return jsonify({
                "available": False,
                "error": "STT not configured"
            })

        status = assaultron.stt_manager.get_status()
        status["available"] = True
        return jsonify(status)

    except Exception as e:
        return jsonify({"available": False, "error": str(e)})


@app.route('/api/stt/events')
@limiter.exempt
def stt_events():
    """Server-Sent Events stream for real-time transcription"""
    def event_stream():
        # Create a queue for this client
        client_queue = Queue()

        # Add queue to STT manager and broadcast list
        if assaultron.stt_manager:
            assaultron.stt_manager.add_event_queue(client_queue)
        assaultron.stt_event_queues.append(client_queue)

        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"

            # Listen for events
            while True:
                try:
                    # Wait for events with timeout to send keepalive
                    message = client_queue.get(timeout=30)
                    yield f"data: {json.dumps(message)}\n\n"
                except:
                    # Send keepalive comment every 30 seconds
                    yield ": keepalive\n\n"
        except GeneratorExit:
            # Client disconnected
            if assaultron.stt_manager:
                assaultron.stt_manager.remove_event_queue(client_queue)
            if client_queue in assaultron.stt_event_queues:
                assaultron.stt_event_queues.remove(client_queue)

    return Response(event_stream(), mimetype='text/event-stream')


@app.route('/api/stt/devices')
@limiter.exempt
def list_stt_devices():
    """List available microphone devices"""
    try:
        if not assaultron.stt_manager:
            return jsonify({"devices": [], "error": "STT not available"}), 503

        from stt_manager import MistralSTTManager
        devices = MistralSTTManager.list_audio_devices()

        return jsonify({"devices": devices})

    except Exception as e:
        return jsonify({"devices": [], "error": str(e)}), 500


@app.route('/api/stt/set_device', methods=['POST'])
def set_stt_device():
    """Change the microphone device"""
    try:
        if not assaultron.stt_manager:
            return jsonify({"success": False, "error": "STT not available"}), 503

        data = request.get_json()
        device_index = data.get('device_index')

        # Convert to int or None
        if device_index is not None and device_index != "":
            device_index = int(device_index)
        else:
            device_index = None

        success = assaultron.stt_manager.set_device(device_index)

        if success:
            device_info = assaultron.stt_manager.get_current_device()
            device_name = device_info['name'] if device_info else "System Default"

            assaultron.log_event(f"STT device changed to: {device_name}", "STT")

            return jsonify({
                "success": True,
                "device_index": device_index,
                "device_name": device_name
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to set device"
            }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/stt/clear', methods=['POST'])
def clear_stt_transcript():
    """Clear the STT transcript buffer (useful when switching modes)"""
    try:
        if not assaultron.stt_manager:
            return jsonify({"success": False, "error": "STT not available"}), 503

        assaultron.stt_manager.clear_transcript_buffer()
        assaultron.log_event("Transcript buffer cleared", "STT")

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@app.route('/api/monitoring/discord_status', methods=['POST'])
@auth.login_required
def update_discord_status():
    """Update Discord bot status in monitoring system"""
    try:
        data = request.get_json()
        active = data.get('active', False)

        if MONITORING_ENABLED:
            monitoring.get_collector().update_system_status(discord_bot_active=active)
            return jsonify({"success": True, "discord_bot_active": active}), 200
        else:
            return jsonify({"success": False, "error": "Monitoring not enabled"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
# VISION SYSTEM ENDPOINTS
# ============================================================================

@app.route('/api/vision/status')
def get_vision_status():
    """Get current vision system status"""
    state = assaultron.vision_system.get_state()
    return jsonify(state.to_dict())


@app.route('/api/vision/cameras')
def get_available_cameras():
    """List available cameras"""
    cameras = assaultron.vision_system.enumerate_cameras()
    return jsonify({
        "cameras": cameras,
        "current_camera": assaultron.vision_system.state.camera_id
    })


@app.route('/api/vision/select_camera', methods=['POST'])
def select_camera():
    """Select a camera by ID"""
    data = request.get_json()
    camera_id = data.get('camera_id', 0)
    
    try:
        camera_id = int(camera_id)
        success = assaultron.vision_system.select_camera(camera_id)
        return jsonify({
            "success": success,
            "camera_id": camera_id
        })
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid camera ID: {e}"}), 400


@app.route('/api/vision/start', methods=['POST'])
def start_vision():
    """Start vision capture"""
    try:
        success = assaultron.vision_system.start_capture()
        if success:
            assaultron.log_event("Vision system started", "VISION")
            
            # Start background monitoring dynamically when vision is enabled
            assaultron.start_background_monitoring()
            
            return jsonify({
                "success": True,
                "message": "Vision capture started"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to start vision capture"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/vision/stop', methods=['POST'])
def stop_vision():
    """Stop vision capture"""
    try:
        assaultron.vision_system.stop_capture()
        assaultron.log_event("Vision system stopped", "VISION")
        return jsonify({
            "success": True,
            "message": "Vision capture stopped"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/vision/toggle', methods=['POST'])
def toggle_vision():
    """Toggle vision capture on/off"""
    try:
        new_state = assaultron.vision_system.toggle_capture()
        status = "started" if new_state else "stopped"
        assaultron.log_event(f"Vision system {status}", "VISION")
        
        # Start background monitoring if vision was enabled
        if new_state:
            assaultron.start_background_monitoring()
            
        return jsonify({
            "success": True,
            "enabled": new_state,
            "message": f"Vision capture {status}"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/vision/frame')
def get_vision_frame():
    """Get current frame as base64 JPEG"""
    frame_b64 = assaultron.vision_system.get_frame_b64()
    if frame_b64:
        return jsonify({
            "success": True,
            "frame": frame_b64,
            "timestamp": datetime.now().isoformat()
        })
    else:
        return jsonify({
            "success": False,
            "error": "No frame available"
        }), 404


@app.route('/api/vision/entities')
def get_vision_entities():
    """Get currently detected entities"""
    state = assaultron.vision_system.get_state()
    return jsonify({
        "entities": [e.to_dict() for e in state.entities],
        "person_count": state.person_count,
        "object_count": state.object_count,
        "scene_description": state.scene_description,
        "threat_assessment": state.threat_assessment
    })


@app.route('/api/vision/scene')
def get_vision_scene():
    """Get scene description for AI context"""
    data = assaultron.vision_system.get_scene_for_cognitive_layer()
    return jsonify(data)


@app.route('/api/vision/confidence', methods=['POST'])
def set_detection_confidence():
    """Set detection confidence threshold"""
    data = request.get_json()
    confidence = data.get('confidence', 0.5)
    
    try:
        confidence = float(confidence)
        assaultron.vision_system.set_detection_confidence(confidence)
        return jsonify({
            "success": True,
            "confidence": confidence
        })
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid confidence value: {e}"}), 400


@app.route('/api/settings/provider', methods=['GET', 'POST'])
def handle_provider_settings():
    """Get or set the AI provider (ollama/gemini)"""
    if request.method == 'POST':
        data = request.get_json()
        provider = data.get('provider')
        if not provider:
            return jsonify({"error": "Provider not specified"}), 400
            
        try:
            success = assaultron.cognitive_engine.switch_provider(provider)
            if success:
                return jsonify({"success": True, "provider": provider})
            else:
                return jsonify({"error": "Failed to switch provider (check logs/keys)"}), 500
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
            
    # GET request
    current_model = Config.OPENROUTER_MODEL if Config.LLM_PROVIDER == "openrouter" else (Config.GEMINI_MODEL if Config.LLM_PROVIDER == "gemini" else Config.AI_MODEL)
    return jsonify({
        "provider": Config.LLM_PROVIDER,
        "model": current_model
    })


# ============================================================================
# AUTONOMOUS AGENT ENDPOINTS
# ============================================================================

@app.route('/api/agent/task', methods=['POST'])
@limiter.limit("10 per minute")
def agent_task():
    """
    Submit a task to the autonomous agent.
    The agent will execute the task in the background.
    """
    data = request.get_json()
    task = data.get('task', '').strip()
    
    if not task:
        return jsonify({"error": "Empty task"}), 400
    
    # Generate task ID
    task_id = f"task_{int(time.time())}_{len(assaultron.agent_tasks)}"
    
    # Progress callback for updates
    progress_updates = []
    
    def progress_callback(update):
        progress_updates.append(update)
        assaultron.log_event(f"Agent [{task_id}]: {update.get('type', 'update')}", "AGENT")
    
    # Start agent task in background thread
    def run_agent_task():
        try:
            assaultron.log_event(f"Starting agent task: {task}", "AGENT")
            result = assaultron.agent_logic.execute_task(task, callback=progress_callback)
            
            # Store result
            assaultron.agent_tasks[task_id] = {
                "task": task,
                "status": "completed" if result.get("success") else "failed",
                "result": result,
                "progress": progress_updates,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Send final message to user
            if result.get("success"):
                final_message = f"Task completed: {result.get('result', 'Done')}"
            else:
                final_message = f"Task failed: {result.get('error', 'Unknown error')}"
            
            # Queue voice message if enabled
            if assaultron.voice_enabled:
                assaultron.voice_system.synthesize_async(final_message)
            
            assaultron.log_event(f"Agent task completed: {task_id}", "AGENT")
            
        except Exception as e:
            assaultron.log_event(f"Agent task error: {e}", "ERROR")
            assaultron.agent_tasks[task_id] = {
                "task": task,
                "status": "error",
                "error": str(e),
                "progress": progress_updates,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    
    # Start background thread
    thread = threading.Thread(target=run_agent_task, daemon=True)
    thread.start()
    
    # Initialize task tracking
    assaultron.agent_tasks[task_id] = {
        "task": task,
        "status": "running",
        "progress": progress_updates,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "Agent task started"
    })


@app.route('/api/agent/status/<task_id>')
def agent_status(task_id):
    """Get the status of an agent task."""
    if task_id not in assaultron.agent_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task_info = assaultron.agent_tasks[task_id]
    
    return jsonify({
        "task_id": task_id,
        "task": task_info["task"],
        "status": task_info["status"],
        "progress": task_info.get("progress", []),
        "result": task_info.get("result"),
        "error": task_info.get("error"),
        "timestamp": task_info["timestamp"]
    })


@app.route('/api/agent/tasks')
def agent_tasks():
    """List all agent tasks."""
    tasks = []
    for task_id, task_info in assaultron.agent_tasks.items():
        tasks.append({
            "task_id": task_id,
            "task": task_info["task"],
            "status": task_info["status"],
            "timestamp": task_info["timestamp"]
        })
    
    return jsonify({"tasks": tasks, "count": len(tasks)})


@app.route('/api/agent/stop/<task_id>', methods=['POST'])
def agent_stop(task_id):
    """Stop a running agent task."""
    if task_id not in assaultron.agent_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task_info = assaultron.agent_tasks[task_id]
    
    if task_info["status"] != "running":
        return jsonify({"error": "Task is not running"}), 400
    
    # Stop the agent
    assaultron.agent_logic.stop()
    task_info["status"] = "stopped"
    
    return jsonify({"success": True, "message": "Agent task stopped"})


# ============================================================================
# EMAIL & GIT MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/api/email/send', methods=['POST'])
@auth.login_required
def send_email():
    """Send an email"""
    from email_manager import get_email_manager

    data = request.get_json()
    to = data.get('to')
    subject = data.get('subject')
    body = data.get('body')
    body_html = data.get('body_html')
    cc = data.get('cc')
    bcc = data.get('bcc')
    add_signature = data.get('add_signature', True)

    if not to or not subject or not body:
        return jsonify({"error": "Missing required fields: to, subject, body"}), 400

    email_manager = get_email_manager()
    success, error = email_manager.send_email(to, subject, body, body_html, cc, bcc, add_signature)

    if success:
        result = {
            "success": True,
            "message": "Email sent successfully",
            "to": to,
            "subject": subject
        }
        if cc:
            result["cc"] = cc
        if bcc:
            result["bcc"] = f"{len(bcc)} recipient(s)" if isinstance(bcc, list) else bcc
        return jsonify(result)
    else:
        return jsonify({
            "success": False,
            "error": error
        }), 400


@app.route('/api/email/read', methods=['GET'])
@auth.login_required
def read_emails():
    """Read emails from inbox"""
    from email_manager import get_email_manager

    folder = request.args.get('folder', 'INBOX')
    limit = int(request.args.get('limit', 5))
    unread_only = request.args.get('unread_only', 'true').lower() == 'true'

    email_manager = get_email_manager()
    emails, error = email_manager.read_emails(folder, limit, unread_only)

    if error:
        return jsonify({
            "success": False,
            "error": error
        }), 400

    return jsonify({
        "success": True,
        "count": len(emails),
        "emails": emails,
        "folder": folder
    })


@app.route('/api/email/status', methods=['GET'])
@auth.login_required
def get_email_status():
    """Get email manager status"""
    from email_manager import get_email_manager

    email_manager = get_email_manager()
    status = email_manager.get_status()

    return jsonify(status)


@app.route('/api/email/reply', methods=['POST'])
@auth.login_required
def reply_email():
    """Reply to an email"""
    from email_manager import get_email_manager

    data = request.get_json()
    email_id = data.get('email_id')
    reply_body = data.get('reply_body')
    reply_body_html = data.get('reply_body_html')
    cc = data.get('cc')
    folder = data.get('folder', 'INBOX')

    if not email_id or not reply_body:
        return jsonify({"error": "Missing required fields: email_id, reply_body"}), 400

    email_manager = get_email_manager()
    success, error = email_manager.reply_to_email(email_id, reply_body, reply_body_html, cc, folder)

    if success:
        return jsonify({
            "success": True,
            "message": "Reply sent successfully",
            "email_id": email_id
        })
    else:
        return jsonify({
            "success": False,
            "error": error
        }), 400


@app.route('/api/email/forward', methods=['POST'])
@auth.login_required
def forward_email():
    """Forward an email"""
    from email_manager import get_email_manager

    data = request.get_json()
    email_id = data.get('email_id')
    to = data.get('to')
    forward_message = data.get('forward_message')
    cc = data.get('cc')
    folder = data.get('folder', 'INBOX')

    if not email_id or not to:
        return jsonify({"error": "Missing required fields: email_id, to"}), 400

    email_manager = get_email_manager()
    success, error = email_manager.forward_email(email_id, to, forward_message, cc, folder)

    if success:
        return jsonify({
            "success": True,
            "message": "Email forwarded successfully",
            "email_id": email_id,
            "to": to
        })
    else:
        return jsonify({
            "success": False,
            "error": error
        }), 400


@app.route('/api/git/repositories', methods=['GET'])
@auth.login_required
def list_git_repositories():
    """List all git repositories in sandbox"""
    from git_manager import get_git_manager

    git_manager = get_git_manager()
    repos = git_manager.list_repositories()

    return jsonify({
        "success": True,
        "count": len(repos),
        "repositories": repos
    })


@app.route('/api/git/status', methods=['GET'])
@auth.login_required
def get_git_status():
    """Get git repository status"""
    from git_manager import get_git_manager
    from pathlib import Path

    # Get repo_path from query parameter
    repo_path = request.args.get('repo_path')
    if not repo_path:
        return jsonify({"error": "Missing repo_path parameter"}), 400

    git_manager = get_git_manager()

    # Construct full path
    full_path = str(Path(git_manager.sandbox_base) / repo_path)
    status, error = git_manager.get_status(full_path)

    if error:
        return jsonify({
            "success": False,
            "error": error
        }), 400

    return jsonify(status)


@app.route('/api/git/commit', methods=['POST'])
@auth.login_required
def git_commit():
    """Create a git commit"""
    from git_manager import get_git_manager
    from pathlib import Path

    data = request.get_json()
    repo_path = data.get('repo_path')
    message = data.get('message')
    files = data.get('files')  # Optional list of files

    if not repo_path:
        return jsonify({"error": "Missing repo_path"}), 400
    if not message:
        return jsonify({"error": "Missing commit message"}), 400

    git_manager = get_git_manager()

    # Construct full path
    full_path = str(Path(git_manager.sandbox_base) / repo_path)
    success, error = git_manager.commit(full_path, message, files)

    if success:
        return jsonify({
            "success": True,
            "repo_path": repo_path,
            "message": error if error else "Commit created successfully"
        })
    else:
        return jsonify({
            "success": False,
            "error": error
        }), 400


@app.route('/api/git/push', methods=['POST'])
@auth.login_required
def git_push():
    """Push commits to remote repository"""
    from git_manager import get_git_manager
    from pathlib import Path

    data = request.get_json() or {}
    repo_path = data.get('repo_path')
    branch = data.get('branch', 'main')

    if not repo_path:
        return jsonify({"error": "Missing repo_path"}), 400

    git_manager = get_git_manager()

    # Construct full path
    full_path = str(Path(git_manager.sandbox_base) / repo_path)
    success, error = git_manager.push(full_path, branch)

    if success:
        return jsonify({
            "success": True,
            "repo_path": repo_path,
            "branch": branch,
            "message": f"Pushed to {branch}"
        })
    else:
        return jsonify({
            "success": False,
            "error": error
        }), 400


@app.route('/api/git/pull', methods=['POST'])
@auth.login_required
def git_pull():
    """Pull latest changes from remote repository"""
    from git_manager import get_git_manager
    from pathlib import Path

    data = request.get_json() or {}
    repo_path = data.get('repo_path')
    branch = data.get('branch', 'main')

    if not repo_path:
        return jsonify({"error": "Missing repo_path"}), 400

    git_manager = get_git_manager()

    # Construct full path
    full_path = str(Path(git_manager.sandbox_base) / repo_path)
    success, error = git_manager.pull(full_path, branch)

    if success:
        return jsonify({
            "success": True,
            "repo_path": repo_path,
            "branch": branch,
            "message": f"Pulled from {branch}"
        })
    else:
        return jsonify({
            "success": False,
            "error": error
        }), 400


@app.route('/api/git/clone', methods=['POST'])
@auth.login_required
def git_clone():
    """Clone a repository into sandbox"""
    from git_manager import get_git_manager
    from pathlib import Path

    data = request.get_json() or {}
    repo_url = data.get('repo_url')
    repo_path = data.get('repo_path')
    use_ssh = data.get('use_ssh', True)

    if not repo_url:
        return jsonify({"error": "Missing repo_url"}), 400
    if not repo_path:
        return jsonify({"error": "Missing repo_path"}), 400

    git_manager = get_git_manager()

    # Construct full path
    full_path = str(Path(git_manager.sandbox_base) / repo_path)
    success, error = git_manager.clone_repo(repo_url, full_path, use_ssh)

    if success:
        return jsonify({
            "success": True,
            "repo_url": repo_url,
            "repo_path": repo_path,
            "message": "Repository cloned successfully"
        })
    else:
        return jsonify({
            "success": False,
            "error": error
        }), 400


@app.route('/api/git/config', methods=['GET'])
@auth.login_required
def get_git_config():
    """Get git manager configuration"""
    from git_manager import get_git_manager

    git_manager = get_git_manager()
    config = git_manager.get_config_status()

    return jsonify(config)



# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Initialize AI on startup
    threading.Thread(target=assaultron.initialize_ai, daemon=True).start()

    assaultron.log_event("Embodied Assaultron System Starting...", "SYSTEM")
    assaultron.log_event("Architecture: Cognitive → Behavioral → Motion", "SYSTEM")

    app.run(debug=True, host='127.0.0.1', port=8080)
