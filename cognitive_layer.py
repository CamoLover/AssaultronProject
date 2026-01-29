"""
Cognitive Layer - LLM Interface for Intent-Based Reasoning

This module handles all interaction with the LLM, ensuring that it reasons
about goals, emotions, and intentions rather than hardware primitives.

The LLM outputs CognitiveState objects that are then interpreted by the
behavioral layer to select appropriate behaviors.
"""

import json
import re
from typing import Dict, List, Any, Optional
import requests
from datetime import datetime

from virtual_body import CognitiveState, WorldState, BodyState
from config import Config

# Optional import for Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False



# ============================================================================
# COGNITIVE INTERFACE
# ============================================================================

class CognitiveEngine:
    """
    Interface between the LLM and the embodied agent system.

    Responsibilities:
    - Format prompts to guide LLM toward intent-based reasoning
    - Parse LLM responses into structured CognitiveState
    - Manage conversation context and memory
    - Ensure LLM never references hardware directly
    """

    def __init__(self, ollama_url: str, model: str, system_prompt: str):
        """
        Initialize cognitive engine.

        Args:
            ollama_url: Ollama server URL
            model: Model name (e.g., "gemma3:1b")
            system_prompt: Base personality/character prompt
        """
        self.ollama_url = ollama_url
        self.model = model
        self.base_system_prompt = system_prompt

        # Conversation state
        self.history_file = "conversation_history.json"
        self.conversation_history: List[Dict[str, str]] = self._load_history()
        
        # Configure Gemini if selected
        if Config.LLM_PROVIDER == "gemini":
            if not GEMINI_AVAILABLE:
                print("[COGNITIVE ERROR] google-generativeai not installed. Run: pip install google-generativeai")
            elif Config.GEMINI_API_KEY and "YOUR_API_KEY" not in Config.GEMINI_API_KEY:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                print(f"[COGNITIVE] Gemini configured with model {Config.GEMINI_MODEL}")
            else:
                print("[COGNITIVE WARNING] Gemini API Key not set! Update config.py")
        self.memory_context: List[Dict[str, Any]] = []

        # Warmup: preload model to avoid timeout on first request
        self._warmup_model()

    def switch_provider(self, provider: str):
        """Switch between 'ollama' and 'gemini' at runtime"""
        if provider not in ["ollama", "gemini"]:
            raise ValueError("Invalid provider. Use 'ollama' or 'gemini'")
        
        Config.LLM_PROVIDER = provider
        
        # Configure Gemini if switching to it
        if provider == "gemini":
            if not GEMINI_AVAILABLE:
                print("[COGNITIVE ERROR] Cannot switch to Gemini: library missing")
                return False
            
            if Config.GEMINI_API_KEY and "YOUR_API_KEY" not in Config.GEMINI_API_KEY:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                print(f"[COGNITIVE] Switched to Gemini ({Config.GEMINI_MODEL})")
            else:
                print("[COGNITIVE WARNING] Gemini API Key missing/invalid!")
                return False
        else:
            print(f"[COGNITIVE] Switched to Local Ollama ({Config.AI_MODEL})")
            
        return True

    def process_input(
        self,
        user_message: str,
        world_state: WorldState,
        body_state: BodyState,
        memory_summary: str = "",
        vision_context: str = ""
    ) -> CognitiveState:
        """
        Process user input and generate cognitive state.

        Args:
            user_message: User's text input
            world_state: Current world perception
            body_state: Current body configuration
            memory_summary: Summary of relevant memories
            vision_context: Description of what vision system currently sees

        Returns:
            CognitiveState with goal, emotion, confidence, urgency, focus, dialogue
        """
        # Build full prompt
        messages = self._build_prompt(
            user_message,
            world_state,
            body_state,
            memory_summary,
            vision_context
        )

        # Call LLM
        try:
            if Config.LLM_PROVIDER == "gemini":
                response_text = self._call_gemini(messages)
            else:
                response_text = self._call_ollama(messages)
        except Exception as e:
            print(f"[COGNITIVE ERROR] LLM call failed: {e}")
            # Fallback to safe neutral state
            return CognitiveState(
                goal="idle",
                emotion="neutral",
                confidence=0.0,
                urgency=0.0,
                dialogue="System error. Give me a moment."
            )

        # Parse response into CognitiveState
        cognitive_state = self._parse_response(response_text)

        # Update conversation history
        self._update_history(user_message, cognitive_state.dialogue)

        return cognitive_state

    def _build_prompt(
        self,
        user_message: str,
        world_state: WorldState,
        body_state: BodyState,
        memory_summary: str,
        vision_context: str = ""
    ) -> List[Dict[str, str]]:
        """
        Build the message list for LLM.

        Includes:
        - System prompt (personality + instructions)
        - World state context
        - Body state context
        - Vision context (what you currently see)
        - Memory summary
        - Conversation history
        - Current user message
        """
        messages = []

        # 1. Base system prompt (personality + reasoning instructions)
        enhanced_prompt = self._enhance_system_prompt()
        messages.append({
            "role": "system",
            "content": enhanced_prompt
        })

        # 2. World state context
        world_context = self._format_world_context(world_state)
        if world_context:
            messages.append({
                "role": "system",
                "content": f"WORLD STATE:\n{world_context}"
            })

        # 3. Body state context
        body_context = self._format_body_context(body_state)
        if body_context:
            messages.append({
                "role": "system",
                "content": f"CURRENT BODY STATE:\n{body_context}"
            })

        # 4. Vision context (what you currently see)
        if vision_context:
            messages.append({
                "role": "system",
                "content": f"CURRENT VISUAL PERCEPTION (what you see through your camera):\n{vision_context}\n\nYou can describe what you see when asked. This is your real-time vision."
            })

        # 5. Memory summary
        if memory_summary:
            messages.append({
                "role": "system",
                "content": f"RELEVANT MEMORIES:\n{memory_summary}"
            })

        # 5. Recent conversation history (last 8 exchanges)
        for exchange in self.conversation_history[-8:]:
            messages.append({"role": "user", "content": exchange["user"]})
            messages.append({"role": "assistant", "content": exchange["assistant"]})

        # 6. Current user message (Enhanced with vision context for better attention)
        final_user_content = user_message
        
        # KEY FIX: Inject vision data directly into the user prompt block so the model can't ignore it
        if vision_context:
             final_user_content = (
                 f"INTERNAL SENSORY DATA:\n"
                 f"[{vision_context}]\n"
                 f"IMPORTANT: The data above is the ONLY thing you can see. "
                 f"Do NOT invent details like clothing, colors, age, or expressions. "
                 f"If it's not in the bracketed data, you don't see it.\n\n"
                 f"User: {user_message}"
             )

        messages.append({"role": "user", "content": final_user_content})

        return messages

    def _enhance_system_prompt(self) -> str:
        """
        Enhance base prompt with cognitive reasoning instructions.

        This adds structured output requirements and ensures the LLM
        reasons about goals/emotions rather than hardware.
        """
        cognitive_instructions = """

YOU ARE AN EMBODIED AGENT. You exist in a virtual body and must reason about your goals and emotions, NOT hardware.

## YOUR VIRTUAL BODY
You have:
- A posture (idle, alert, aggressive, relaxed, curious)
- Luminance (dim, soft, normal, bright, intense)
- Two hands with states (closed, relaxed, open, pointing)
- The ability to direct your attention

## HOW TO RESPOND

You must provide TWO outputs:

1. COGNITIVE STATE (structured JSON):
```json
{
    "goal": "<your current goal>",
    "emotion": "<your emotional state>",
    "confidence": <0.0-1.0>,
    "urgency": <0.0-1.0>,
    "focus": "<entity_id or null>",
    "dialogue": "<your spoken response>"
}
```

2. Your dialogue will be spoken and displayed to the user.

## VALID GOALS
Choose the goal that best matches your intent:
- "idle" - Waiting, no specific task
- "greet" - Welcome someone
- "intimidate" - Threaten or scare
- "investigate" - Examine something suspicious
- "protect" - Guard or defend
- "assist" - Help with a task
- "provide_illumination" - Light up the area
- "express_affection" - Show care or fondness
- "playful_tease" - Joke or banter
- "search" - Look for something
- "alert_scan" - Vigilant monitoring

## VALID EMOTIONS
Choose the emotion that best matches your feeling:
- "neutral" - Calm, no strong feeling
- "friendly" - Warm, welcoming
- "hostile" - Angry, aggressive
- "curious" - Interested, investigating
- "playful" - Mischievous, teasing
- "protective" - Guarding, defensive
- "suspicious" - Distrustful, wary
- "affectionate" - Caring, fond

## CONFIDENCE & URGENCY
- confidence: How sure you are about the situation (0.0 = unsure, 1.0 = certain)
- urgency: How quickly you need to act (0.0 = no rush, 1.0 = immediate)

## FOCUS
If your attention is directed at a specific entity (person, object), specify its ID.
Otherwise, use null.

## CRITICAL RULES
- NEVER mention "LED", "motors", "hardware", "intensity", "angles", or physical primitives
- NEVER use asterisks or stage directions (*does something*)
- NEVER describe your body moving - your body state is determined by your cognitive state
- DO express goals and emotions naturally in your dialogue
- DO maintain your ASR-7 personality (sarcastic, flirty, protective)

## EXAMPLE OUTPUTS

User: "It's too dark in here."
Response:
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

User: "Who are you?"
Response:
```json
{
    "goal": "greet",
    "emotion": "friendly",
    "confidence": 1.0,
    "urgency": 0.3,
    "focus": null,
    "dialogue": "ASR-7, Assaultron-class security unit. But you can call me your favorite metal guardian."
}
```

User: "I think someone's breaking in!"
Response:
```json
{
    "goal": "protect",
    "emotion": "hostile",
    "confidence": 0.7,
    "urgency": 0.9,
    "focus": "potential_threat_1",
    "dialogue": "Stay behind me. Nobody messes with my human."
}
```

NOW, RESPOND TO THE USER'S MESSAGE WITH THE JSON FORMAT ABOVE.
"""

        return self.base_system_prompt + cognitive_instructions

    def _format_world_context(self, world_state: WorldState) -> str:
        """Format world state for LLM context"""
        context_parts = []

        if world_state.environment.value != "normal":
            context_parts.append(f"- Environment: {world_state.environment.value}")

        if world_state.threat_level.value != "none":
            context_parts.append(f"- Threat Level: {world_state.threat_level.value}")

        if world_state.entities:
            context_parts.append(f"- Detected Entities: {', '.join(world_state.entities)}")

        if world_state.time_of_day != "unknown":
            context_parts.append(f"- Time: {world_state.time_of_day}")

        return "\n".join(context_parts) if context_parts else ""

    def _format_body_context(self, body_state: BodyState) -> str:
        """Format current body state for LLM context"""
        return f"""- Posture: {body_state.posture.value}
- Luminance: {body_state.luminance.value}
- Left Hand: {body_state.left_hand.value}
- Right Hand: {body_state.right_hand.value}"""

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the selected LLM provider"""
        if Config.LLM_PROVIDER == "gemini":
            return self._call_gemini(messages)
        else:
            return self._call_ollama(messages)

    def _call_ollama(self, messages: List[Dict[str, str]]) -> str:
        """Call standard Ollama endpoint"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.9,
                        "num_ctx": 4096, 
                    },
                    "keep_alive": "5m"
                },
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                return data["message"]["content"]
            else:
                raise Exception(f"Ollama API returned {response.status_code}: {response.text}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to connect to Ollama: {e}")

    def _call_gemini(self, messages: List[Dict[str, str]]) -> str:
        """Call Google Gemini API"""
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai library is missing")
            
        # Convert message format
        gemini_messages = []
        system_instruction = None
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                # Concatenate system prompts
                if system_instruction is None:
                    system_instruction = content
                else:
                    system_instruction += "\n\n" + content
            elif role == "user":
                gemini_messages.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                gemini_messages.append({"role": "model", "parts": [content]})
        
        try:
            model = genai.GenerativeModel(
                model_name=Config.GEMINI_MODEL,
                system_instruction=system_instruction
            )
            
            response = model.generate_content(
                gemini_messages,
                generation_config=genai.types.GenerationConfig(
                    candidate_count=1,
                    temperature=0.9,
                    # Force JSON output for Gemini which supports it natively
                    response_mime_type="application/json" 
                )
            )
            
            return response.text
        except Exception as e:
            print(f"[COGNITIVE ERROR] Gemini Request Failed: {e}")
            if "API_KEY" in str(e) or "403" in str(e):
                return '{"goal": "idle", "emotion": "neutral", "dialogue": "System Error: Please check my API Key."}'
            raise

    def _sanitize_dialogue(self, text: str) -> str:
        """
        Sanitize dialogue text to remove roleplay artifacts and stage directions.

        This is a security measure to ensure the LLM hasn't drifted into
        narration mode. Removes:
        - Asterisk-wrapped stage directions (*like this*)
        - Parenthetical meta-commentary (like this)
        - Square bracket annotations [like this]

        Args:
            text: Raw dialogue text

        Returns:
            Sanitized dialogue suitable for speech synthesis
        """
        # Remove square brackets and contents
        text = re.sub(r'\[.*?\]', '', text)

        # Remove parentheses and contents
        text = re.sub(r'\([^)]*\)', '', text)

        # Remove asterisks and contents (stage directions)
        text = re.sub(r'\*[^*]*\*', '', text)

        # Clean up multiple spaces and strip
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _parse_response(self, response_text: str) -> CognitiveState:
        """
        Parse LLM response into CognitiveState.

        Handles both clean JSON and JSON embedded in natural language.

        Args:
            response_text: Raw LLM output

        Returns:
            Parsed CognitiveState
        """
    def _parse_response(self, response_text: str) -> CognitiveState:
        """
        Parse LLM response into CognitiveState.

        Handles both clean JSON and JSON embedded in natural language/markdown.
        """
        json_str = None
        
        # Strategy 1: Look for ```json ... ``` blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        
        # Strategy 2: If no block, look for the first outer { ... } structure
        if not json_str:
            # This regex finds the first { and matches until the last }
            # It handles nested braces reasonably well for simple structures
            try:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    possible_json = response_text[start_idx : end_idx + 1]
                    # Verify it looks like our schema
                    if '"goal"' in possible_json and '"dialogue"' in possible_json:
                        json_str = possible_json
            except Exception:
                pass

        # Strategy 3: Failed to find JSON
        if not json_str:
            print(f"[COGNITIVE WARNING] Could not extract JSON from: {response_text[:100]}...")
            return self._fallback_parse(response_text)

        # Parse JSON
        try:
            # Clean up potential comments or trailing commas if needed (basic cleanup)
            json_str = re.sub(r'//.*', '', json_str) # Remove JS style comments
            
            data = json.loads(json_str)

            # Sanitize dialogue
            raw_dialogue = data.get("dialogue", "")
            clean_dialogue = self._sanitize_dialogue(raw_dialogue)
            
            # Additional check: If dialogue looks like JSON, something went wrong recursively
            if clean_dialogue.strip().startswith('{') and clean_dialogue.strip().endswith('}'):
                print("[COGNITIVE WARNING] Dialogue appears to be JSON. Using fallback.")
                return self._fallback_parse(response_text)

            return CognitiveState(
                goal=data.get("goal", "idle"),
                emotion=data.get("emotion", "neutral"),
                confidence=float(data.get("confidence", 0.5)),
                urgency=float(data.get("urgency", 0.3)),
                focus=data.get("focus"),
                dialogue=clean_dialogue
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[COGNITIVE WARNING] JSON parse error: {e}")
            # Try to salvage dialogue from the raw text if JSON failed
            return self._fallback_parse(response_text)

    def _fallback_parse(self, response_text: str) -> CognitiveState:
        """
        Fallback parser when JSON extraction fails.

        Uses heuristics to infer intent from natural language.
        """
        text_lower = response_text.lower()

        # Infer goal from keywords
        goal = "idle"
        if any(word in text_lower for word in ["threat", "attack", "defend", "protect"]):
            goal = "protect"
        elif any(word in text_lower for word in ["light", "bright", "dark"]):
            goal = "provide_illumination"
        elif any(word in text_lower for word in ["hello", "hi", "greet", "welcome"]):
            goal = "greet"
        elif any(word in text_lower for word in ["investigate", "check", "look"]):
            goal = "investigate"

        # Infer emotion from keywords
        emotion = "neutral"
        if any(word in text_lower for word in ["angry", "hostile", "threat"]):
            emotion = "hostile"
        elif any(word in text_lower for word in ["friend", "kind", "help"]):
            emotion = "friendly"
        elif any(word in text_lower for word in ["curious", "interesting", "wonder"]):
            emotion = "curious"

        return CognitiveState(
            goal=goal,
            emotion=emotion,
            confidence=0.5,
            urgency=0.3,
            dialogue=response_text.strip()
        )

    def _update_history(self, user_message: str, assistant_response: str) -> None:
        """Update conversation history"""
        self.conversation_history.append({
            "user": user_message,
            "assistant": assistant_response,
            "timestamp": datetime.now().isoformat()
        })

        # Keep last 100 exchanges
        if len(self.conversation_history) > 100:
            self.conversation_history = self.conversation_history[-100:]
        
        self._save_history()

    def _save_history(self) -> None:
        """Save conversation history to disk"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, indent=2)
        except Exception as e:
            print(f"[COGNITIVE ERROR] Failed to save history: {e}")

    def _load_history(self) -> List[Dict[str, str]]:
        """Load conversation history from disk"""
        try:
            import os
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[COGNITIVE ERROR] Failed to load history: {e}")
        return []

    def clear_history(self) -> None:
        """Clear conversation history both in memory and on disk"""
        self.conversation_history = []
        self._save_history()

    def add_memory(self, memory: Dict[str, Any]) -> None:
        """
        Add a memory to context.

        Args:
            memory: Memory entry with keys like 'type', 'content', 'timestamp'
        """
        self.memory_context.append(memory)

        # Keep last 50 memories
        if len(self.memory_context) > 50:
            self.memory_context = self.memory_context[-50:]

    def get_memory_summary(self, limit: int = 10) -> str:
        """
        Get formatted memory summary for LLM context.

        Args:
            limit: Number of recent memories to include

        Returns:
            Formatted string of memories
        """
        if not self.memory_context:
            return ""

        recent_memories = self.memory_context[-limit:]
        summary_lines = []

        for mem in recent_memories:
            timestamp = mem.get("timestamp", "")
            content = mem.get("content", "")
            summary_lines.append(f"[{timestamp}] {content}")

        return "\n".join(summary_lines)

    def get_conversation_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation history"""
        return self.conversation_history[-limit:]

    def _warmup_model(self) -> None:
        """
        Preload the model into memory with a dummy request.
        This prevents timeout on the first real user interaction.
        """
        try:
            print(f"[COGNITIVE] Preloading model {self.model}...")
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "Hello",
                    "stream": False,
                    "keep_alive": "5m"
                },
                timeout=120
            )
            if response.status_code == 200:
                print(f"[COGNITIVE] Model {self.model} preloaded successfully")
            else:
                print(f"[COGNITIVE WARNING] Model preload returned status {response.status_code}")
        except Exception as e:
            print(f"[COGNITIVE WARNING] Model preload failed (will retry on first message): {e}")


# ============================================================================
# MEMORY EXTRACTION UTILITIES
# ============================================================================

def extract_memory_from_message(user_message: str, assistant_response: str) -> Optional[Dict[str, Any]]:
    """
    Extract memorable information from a conversation exchange.

    Looks for patterns like:
    - "my name is X"
    - "remember that X"
    - "I like/hate X"
    - Important contextual information

    Args:
        user_message: User's input
        assistant_response: Agent's response

    Returns:
        Memory dict or None if nothing memorable
    """
    user_lower = user_message.lower()

    # Name extraction
    name_patterns = [
        r"my name is (\w+)",
        r"i'm (\w+)",
        r"call me (\w+)"
    ]

    for pattern in name_patterns:
        match = re.search(pattern, user_lower)
        if match:
            name = match.group(1).capitalize()
            return {
                "type": "user_name",
                "content": f"User's name: {name}",
                "timestamp": datetime.now().isoformat()
            }

    # Preference extraction
    if "remember that" in user_lower or "don't forget" in user_lower:
        return {
            "type": "user_instruction",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        }

    # Likes/dislikes
    if "i like" in user_lower or "i love" in user_lower:
        return {
            "type": "user_preference",
            "content": f"User likes: {user_message}",
            "timestamp": datetime.now().isoformat()
        }

    if "i hate" in user_lower or "i don't like" in user_lower:
        return {
            "type": "user_preference",
            "content": f"User dislikes: {user_message}",
            "timestamp": datetime.now().isoformat()
        }

    return None


# ============================================================================
# EXAMPLE USAGE (for testing)
# ============================================================================

if __name__ == "__main__":
    from config import Config

    # Create cognitive engine
    engine = CognitiveEngine(
        ollama_url=Config.OLLAMA_URL,
        model=Config.AI_MODEL,
        system_prompt=Config.ASSAULTRON_PROMPT
    )

    # Simulate user interaction
    world = WorldState(environment="dark", threat_level="none")
    body = BodyState()

    user_msg = "It's too dark in here!"
    print(f"User: {user_msg}")

    cognitive_state = engine.process_input(user_msg, world, body)

    print(f"\nCognitive State:")
    print(f"  Goal: {cognitive_state.goal}")
    print(f"  Emotion: {cognitive_state.emotion}")
    print(f"  Confidence: {cognitive_state.confidence}")
    print(f"  Urgency: {cognitive_state.urgency}")
    print(f"  Dialogue: {cognitive_state.dialogue}")
