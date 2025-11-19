from flask import Flask, render_template, request, jsonify
import threading
import time
import json
from datetime import datetime
import requests
from config import Config
import psutil
from voicemanager import VoiceManager

app = Flask(__name__)
config = Config()


class AssaultronCore:
    def __init__(self):
        self.conversation_history = []
        self.memory_context = []  # Enhanced memory for key information
        self.system_logs = []
        self.status = "Initializing..."
        self.ai_active = False
        self.start_time = datetime.now()
        self.performance_stats = {
            "total_requests": 0,
            "avg_response_time": 0,
            "last_response_time": 0
        }
        
        # Hardware state tracking
        self.hardware_state = {
            "led_intensity": 50,  # 0-100 percentage
            "hands": {
                "left": {"position": 0, "status": "closed"},    # 0-100 (closed to open)
                "right": {"position": 0, "status": "closed"}
            }
        }
        
        # Initialize voice system with VoiceManager
        self.voice_system = VoiceManager(logger=self)
        self.voice_enabled = False
        
    def log_event(self, message, event_type="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "type": event_type,
            "message": message
        }
        self.system_logs.append(log_entry)
        print(f"[{timestamp}] {event_type}: {message}")
        
    def process_actions(self, text):
        """Extract and execute action commands from AI response"""
        import re
        actions_executed = []
        
        # LED Intensity Control
        led_match = re.search(r'\[LED_INTENSITY:(\d+)\]', text)
        if led_match:
            intensity = int(led_match.group(1))
            if 0 <= intensity <= 100:
                self.hardware_state["led_intensity"] = intensity
                actions_executed.append(f"LED_INTENSITY set to {intensity}%")
                self.log_event(f"LED intensity set to {intensity}%", "ACTION")
        
        # Hand Movement Control
        hand_matches = re.findall(r'\[HAND_(LEFT|RIGHT)_(OPEN|CLOSE):(\d+)\]', text)
        for hand, action, value in hand_matches:
            hand_key = hand.lower()
            raw_position = int(value)
            
            if 0 <= raw_position <= 100:
                # CRITICAL FIX: Handle CLOSE vs OPEN commands correctly
                if action == "CLOSE":
                    # For CLOSE commands, invert the value (100 = fully closed = position 0)
                    position = 100 - raw_position
                else:  # OPEN
                    # For OPEN commands, use value directly (100 = fully open = position 100)
                    position = raw_position
                
                self.hardware_state["hands"][hand_key]["position"] = position
                
                # Update status based on final position
                if position <= 10:
                    self.hardware_state["hands"][hand_key]["status"] = "closed"
                elif position >= 90:
                    self.hardware_state["hands"][hand_key]["status"] = "open_max"
                else:
                    self.hardware_state["hands"][hand_key]["status"] = f"open_{position}%"
                
                action_desc = f"Hand {hand_key} {action.lower()} to {raw_position}% (final position: {position}%)"
                actions_executed.append(action_desc)
                self.log_event(action_desc, "ACTION")
        
        return actions_executed
    
    def analyze_context_and_suggest_actions(self, user_message):
        """Analyze user message for contextual cues and suggest actions to AI"""
        import re
        user_lower = user_message.lower()
        context_additions = []
        
        # Check for time/date requests ONLY (very specific phrases)
        time_phrases = ["what time is it", "current time", "time now", "what's the time", "tell me the time"]
        date_phrases = ["what date", "today's date", "what day is it", "current date", "what's today's date"]
        
        if any(phrase in user_lower for phrase in time_phrases):
            context_additions.append("TOOL_REQUEST: User asking for current time. Use get_time tool.")
            return context_additions
        elif any(phrase in user_lower for phrase in date_phrases):
            context_additions.append("TOOL_REQUEST: User asking for current date. Use get_date tool.")
            return context_additions
        
        # Skip context analysis for other conversational questions that don't need hardware
        conversation_keywords = [
            "who", "where", "why", "how", "tell me", "explain", 
            "thanks", "thank you", "hello", "hi", "good", "ok", "okay", "nice",
            "created", "made", "built", "weather"
        ]
        
        if any(keyword in user_lower for keyword in conversation_keywords) and \
           not any(action_word in user_lower for action_word in ["grab", "close", "open", "dark", "bright", "light"]):
            return context_additions  # Return empty for pure conversation
        
        # Lighting context detection
        if any(phrase in user_lower for phrase in ["it's dark", "too dark", "can't see", "really dark", "very dark", "too dim"]):
            context_additions.append("ENVIRONMENTAL_ASSESSMENT: Low light conditions detected. Recommend increasing LED intensity to 85-100% for optimal visibility.")
        elif any(phrase in user_lower for phrase in ["too bright", "dim the light", "lower light", "too much light"]):
            context_additions.append("ENVIRONMENTAL_ASSESSMENT: High light conditions detected. Recommend reducing LED intensity to 20-40%.")
        elif any(phrase in user_lower for phrase in ["stealth", "hide", "quiet", "covert"]):
            context_additions.append("TACTICAL_ASSESSMENT: Stealth operations required. Recommend LED intensity 0-10%.")
        
        # Object manipulation context
        grab_match = re.search(r'grab.*?(left|right).*?hand', user_lower)
        if grab_match:
            hand = grab_match.group(1)
            context_additions.append(f"MANIPULATION_COMMAND: Object acquisition requested with {hand} hand. Execute close grip protocol.")
        elif "grab" in user_lower and ("left" in user_lower or "right" in user_lower):
            if "left" in user_lower:
                context_additions.append("MANIPULATION_COMMAND: Left hand object acquisition. Execute close grip protocol.")
            if "right" in user_lower:
                context_additions.append("MANIPULATION_COMMAND: Right hand object acquisition. Execute close grip protocol.")
        elif any(phrase in user_lower for phrase in ["close both hands", "close your hands", "close hands", "both hands"]):
            context_additions.append("MANIPULATION_COMMAND: Close both left and right hands. Use separate commands for each hand.")
        elif any(phrase in user_lower for phrase in ["open hands", "release", "let go", "drop"]):
            context_additions.append("MANIPULATION_COMMAND: Object release requested. Execute open hand protocol.")
        
        # Simple states
        if any(phrase in user_lower for phrase in ["ready", "alert"]):
            context_additions.append("SYSTEM_STATE: Alert mode - increase visibility and prepare hands.")
        elif any(phrase in user_lower for phrase in ["relax", "at ease", "standby"]):
            context_additions.append("SYSTEM_STATE: Standby mode - reduce power consumption.")
        
        return context_additions
    
    def validate_action_execution(self, ai_response, actions_executed):
        """Check if AI described actions without proper tag execution"""
        import re
        response_lower = ai_response.lower()
        
        # Check for action descriptions without corresponding tags
        action_words = [
            "increasing led", "reducing led", "setting led", "led intensity",
            "closed hand", "closing hand", "opened hand", "opening hand",
            "grip protocol", "grab", "executing", "manipulator"
        ]
        
        described_actions = []
        for word in action_words:
            if word in response_lower:
                described_actions.append(word)
        
        if described_actions and len(actions_executed) == 0:
            self.log_event(f"WARNING: AI described actions {described_actions} but no hardware tags executed", "WARNING")
        elif len(described_actions) > len(actions_executed):
            self.log_event(f"WARNING: AI described more actions than executed. Described: {len(described_actions)}, Executed: {len(actions_executed)}", "WARNING")
    
    def add_to_memory(self, user_msg, ai_response):
        """Add important context to long-term memory"""
        # Extract key information patterns
        import re
        
        # Look for important context markers
        memory_triggers = [
            r"my name is (\w+)",
            r"i am (\w+)",
            r"call me (\w+)",
            r"remember that (.*)",
            r"important: (.*)",
            r"note: (.*)"
        ]
        
        for trigger in memory_triggers:
            matches = re.findall(trigger, user_msg.lower())
            for match in matches:
                memory_entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "context",
                    "content": match,
                    "source": "user_input"
                }
                self.memory_context.append(memory_entry)
                self.log_event(f"Added to memory: {match}", "MEMORY")
        
        # Limit memory to last 50 entries
        if len(self.memory_context) > 50:
            self.memory_context = self.memory_context[-50:]
    
    def execute_tool(self, tool_name, params=None):
        """Execute a tool and return the result"""
        if params is None:
            params = {}
        
        try:
            if tool_name == "get_time":
                return self.tool_get_time()
            elif tool_name == "get_date":
                return self.tool_get_date()
            # Future tools can be added here:
            # elif tool_name == "camera_scan":
            #     return self.tool_camera_scan(params)
            # elif tool_name == "sensor_reading":
            #     return self.tool_sensor_reading(params.get("sensor_type"))
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
    
    def tool_get_time(self):
        """Get current time"""
        current_time = datetime.now()
        return {
            "success": True,
            "time": current_time.strftime("%H:%M:%S"),
            "formatted": current_time.strftime("%I:%M %p"),
            "timestamp": current_time.isoformat()
        }
    
    def tool_get_date(self):
        """Get current date"""
        current_date = datetime.now()
        return {
            "success": True,
            "date": current_date.strftime("%Y-%m-%d"),
            "formatted": current_date.strftime("%A, %B %d, %Y"),
            "day_of_week": current_date.strftime("%A")
        }
    
    def process_tool_requests(self, text):
        """Extract and execute tool requests from AI response"""
        import re
        tools_executed = []
        
        # Look for tool requests in format [TOOL:tool_name] or [TOOL:tool_name:params]
        tool_matches = re.findall(r'\[TOOL:([^:]+)(?::([^]]+))?\]', text)
        
        for tool_name, params_str in tool_matches:
            params = {}
            if params_str:
                # Simple parameter parsing - can be extended
                try:
                    # Format: param1=value1,param2=value2
                    for param in params_str.split(','):
                        if '=' in param:
                            key, value = param.split('=', 1)
                            params[key.strip()] = value.strip()
                except:
                    pass
            
            result = self.execute_tool(tool_name, params)
            tools_executed.append({
                "tool": tool_name,
                "params": params,
                "result": result
            })
            
            self.log_event(f"Tool executed: {tool_name} -> {result}", "TOOL")
        
        return tools_executed
    
    def inject_tool_results(self, ai_response, tools_executed):
        """Replace tool tags in AI response with actual tool results"""
        import re
        
        if not tools_executed:
            return ai_response
        
        modified_response = ai_response
        
        for tool_exec in tools_executed:
            tool_name = tool_exec["tool"]
            result = tool_exec["result"]
            
            # Find the tool tag in the response
            pattern = rf'\[TOOL:{re.escape(tool_name)}(?::[^\]]+)?\]'
            
            if result.get("success"):
                if tool_name == "get_time":
                    replacement = f"It's {result['formatted']}."
                elif tool_name == "get_date":
                    replacement = f"Today is {result['formatted']}."
                else:
                    replacement = str(result)
            else:
                replacement = f"Tool error: {result.get('error', 'Unknown error')}"
            
            # Replace the tool tag with the result
            modified_response = re.sub(pattern, replacement, modified_response, count=1)
        
        return modified_response
        
    def send_to_ai(self, message):
        """Send message to Ollama AI model"""
        start_time = time.time()
        try:
            self.log_event(f"Sending message to AI: {message[:50]}...", "AI")
            
            # Prepare the conversation context
            messages = [
                {"role": "system", "content": config.ASSAULTRON_PROMPT},
            ]
            
            # Add memory context if available
            if self.memory_context:
                memory_summary = "MEMORY BANKS: "
                for mem in self.memory_context[-10:]:  # Last 10 memory entries
                    memory_summary += f"{mem['content']}; "
                messages.append({"role": "system", "content": memory_summary})
            
            # Analyze user message for contextual cues
            context_cues = self.analyze_context_and_suggest_actions(message)
            if context_cues:
                context_msg = "CONTEXTUAL_ANALYSIS: " + " ".join(context_cues)
                messages.append({"role": "system", "content": context_msg})
                self.log_event(f"Context detected: {len(context_cues)} cues", "CONTEXT")
            
            # Add recent conversation history
            for entry in self.conversation_history[-8:]:  # Increased from 5 to 8 for better context
                messages.append({"role": "user", "content": entry["user"]})
                messages.append({"role": "assistant", "content": entry["assistant"]})
            
            messages.append({"role": "user", "content": message})
            
            # Send to Ollama
            response = requests.post(f"{config.OLLAMA_URL}/api/chat", 
                json={
                    "model": config.AI_MODEL,
                    "messages": messages,
                    "stream": False
                },
                timeout=30
            )
            
            response_time = round((time.time() - start_time) * 1000)  # Convert to ms
            
            if response.status_code == 200:
                ai_response = response.json()["message"]["content"]
                
                # Update performance stats
                self.performance_stats["total_requests"] += 1
                self.performance_stats["last_response_time"] = response_time
                
                # Calculate rolling average
                if self.performance_stats["avg_response_time"] == 0:
                    self.performance_stats["avg_response_time"] = response_time
                else:
                    self.performance_stats["avg_response_time"] = round(
                        (self.performance_stats["avg_response_time"] + response_time) / 2
                    )
                
                # Process actions from AI response
                actions_executed = self.process_actions(ai_response)
                
                # Process tool requests from AI response
                tools_executed = self.process_tool_requests(ai_response)
                
                # Replace tool placeholders with actual results
                original_response = ai_response
                ai_response = self.inject_tool_results(ai_response, tools_executed)
                if tools_executed:
                    self.log_event(f"Tool injection: '{original_response}' → '{ai_response}'", "TOOL")
                
                # Check for action descriptions without proper tags
                self.validate_action_execution(ai_response, actions_executed)
                
                # Add to memory
                self.add_to_memory(message, ai_response)
                
                # Add to conversation history
                self.conversation_history.append({
                    "user": message,
                    "assistant": ai_response,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "response_time": response_time,
                    "actions": actions_executed,
                    "tools": tools_executed
                })
                
                self.log_event(f"AI Response received ({response_time}ms): {ai_response[:50]}...", "AI")
                
                # Generate voice if enabled
                if self.voice_enabled:
                    self.voice_system.synthesize_async(ai_response)
                
                return ai_response
            else:
                error_msg = f"AI Error: HTTP {response.status_code}"
                self.log_event(error_msg, "ERROR")
                return "AI communication error occurred."
                
        except Exception as e:
            response_time = round((time.time() - start_time) * 1000)
            error_msg = f"AI Communication failed: {str(e)}"
            self.log_event(error_msg, "ERROR")
            return "Unable to communicate with AI system."
    
    # Voice system initialization is now handled by the start_server_and_load_model method
    
    def initialize_ai(self):
        """Initialize AI connection"""
        try:
            self.log_event("Initializing AI connection...", "SYSTEM")
            response = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=10)
            if response.status_code == 200:
                self.ai_active = True
                self.status = "AI Online - Assaultron Ready"
                self.log_event("AI connection established successfully", "SYSTEM")
            else:
                self.status = "AI Connection Failed"
                self.log_event("Failed to connect to Ollama", "ERROR")
        except Exception as e:
            self.status = "AI Connection Failed"
            self.log_event(f"AI initialization error: {str(e)}", "ERROR")

# Initialize Assaultron
assaultron = AssaultronCore()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({"error": "Empty message"}), 400
    
    # Get AI response
    ai_response = assaultron.send_to_ai(message)
    
    return jsonify({
        "response": ai_response,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/api/logs')
def get_logs():
    return jsonify(assaultron.system_logs[-50:])  # Last 50 logs

@app.route('/api/status')
def get_status():
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
        "conversation_count": len(assaultron.conversation_history),
        "uptime_seconds": int(uptime_seconds),
        "performance": assaultron.performance_stats,
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent
        }
    })

@app.route('/api/history')
def get_history():
    return jsonify(assaultron.conversation_history[-10:])  # Last 10 conversations

@app.route('/api/hardware')
def get_hardware():
    """Get current hardware state"""
    return jsonify(assaultron.hardware_state)

@app.route('/api/memory')
def get_memory():
    """Get AI memory context"""
    return jsonify(assaultron.memory_context[-20:])  # Last 20 memory entries

@app.route('/api/hardware/led', methods=['POST'])
def set_led():
    """Manually set LED intensity"""
    data = request.get_json()
    intensity = data.get('intensity', 50)
    if 0 <= intensity <= 100:
        assaultron.hardware_state["led_intensity"] = intensity
        assaultron.log_event(f"LED manually set to {intensity}%", "MANUAL")
        return jsonify({"success": True, "intensity": intensity})
    return jsonify({"error": "Invalid intensity value"}), 400

@app.route('/api/hardware/hands', methods=['POST'])
def set_hands():
    """Manually set hand positions"""
    data = request.get_json()
    hand = data.get('hand')  # 'left' or 'right'
    position = data.get('position', 0)
    
    if hand in ['left', 'right'] and 0 <= position <= 100:
        assaultron.hardware_state["hands"][hand]["position"] = position
        if position <= 10:
            assaultron.hardware_state["hands"][hand]["status"] = "closed"
        elif position >= 90:
            assaultron.hardware_state["hands"][hand]["status"] = "open_max"
        else:
            assaultron.hardware_state["hands"][hand]["status"] = f"open_{position}%"
        
        assaultron.log_event(f"Hand {hand} manually set to {position}%", "MANUAL")
        return jsonify({"success": True, "hand": hand, "position": position})
    return jsonify({"error": "Invalid hand or position value"}), 400

@app.route('/api/debug/last_response')
def get_last_response():
    """Get the last AI response for debugging"""
    if assaultron.conversation_history:
        last = assaultron.conversation_history[-1]
        return jsonify({
            "raw_response": last["assistant"],
            "actions_found": last.get("actions", []),
            "tools_found": last.get("tools", []),
            "user_message": last["user"]
        })
    return jsonify({"error": "No conversation history"})

@app.route('/api/tools/execute', methods=['POST'])
def execute_tool():
    """Manually execute a tool"""
    data = request.get_json()
    tool_name = data.get('tool')
    params = data.get('params', {})
    
    if tool_name:
        result = assaultron.execute_tool(tool_name, params)
        return jsonify(result)
    return jsonify({"error": "Tool name required"}), 400

@app.route('/api/tools/available')
def get_available_tools():
    """Get list of available tools"""
    return jsonify({
        "tools": [
            {
                "name": "get_time",
                "description": "Get current time",
                "parameters": []
            },
            {
                "name": "get_date", 
                "description": "Get current date",
                "parameters": []
            }
            # Future tools will be added here
        ]
    })

@app.route('/api/voice/start', methods=['POST'])
def start_voice_server():
    """Start xVAsynth server and load Assaultron voice model"""
    try:
        assaultron.log_event("Starting Assaultron voice system...", "VOICE")
        
        # Run the complete voice startup process
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
    
    # Generate speech asynchronously
    thread = assaultron.voice_system.synthesize_async(text)
    return jsonify({"success": True, "message": "Speech generation started"})

@app.route('/api/voice/status')
def voice_status():
    """Get voice system status"""
    status = assaultron.voice_system.get_status()
    status["voice_enabled"] = assaultron.voice_enabled
    return jsonify(status)

if __name__ == '__main__':
    # Initialize AI on startup
    threading.Thread(target=assaultron.initialize_ai, daemon=True).start()
    
    # Voice system will be initialized manually via web interface
    
    assaultron.log_event("Assaultron System Starting...", "SYSTEM")
    app.run(debug=True, host='127.0.0.1', port=8080)