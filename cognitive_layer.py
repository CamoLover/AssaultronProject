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

from virtual_body import CognitiveState, WorldState, BodyState, MoodState
from config import Config
from time_awareness import get_time_context, format_time_context_for_prompt

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
        
        # Long-term memories
        self.memory_file = "memories.json"

        # Load memories into context from disk
        self.memory_context: List[Dict[str, Any]] = self._load_long_term_memories()

        # Alias for compatibility - both names point to the same list
        self.long_term_memories = self.memory_context

        # Configure Gemini if selected
        if Config.LLM_PROVIDER == "gemini":
            if not GEMINI_AVAILABLE:
                print("[COGNITIVE ERROR] google-generativeai not installed. Run: pip install google-generativeai")
            elif Config.GEMINI_API_KEY and "YOUR_API_KEY" not in Config.GEMINI_API_KEY:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                print(f"[COGNITIVE] Gemini configured with model {Config.GEMINI_MODEL}")
            else:
                print("[COGNITIVE WARNING] Gemini API Key not set! Update config.py")
        
        # Warmup: preload model to avoid timeout on first request
        self._warmup_model()

    def switch_provider(self, provider: str):
        """Switch between 'ollama', 'gemini', or 'openrouter' at runtime"""
        if provider not in ["ollama", "gemini", "openrouter"]:
            raise ValueError("Invalid provider. Use 'ollama', 'gemini', or 'openrouter'")
        
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
        elif provider == "openrouter":
            if Config.OPENROUTER_API_KEY and "YOUR_API_KEY" not in Config.OPENROUTER_API_KEY:
                print(f"[COGNITIVE] Switched to OpenRouter ({Config.OPENROUTER_MODEL})")
            else:
                print("[COGNITIVE WARNING] OpenRouter API Key missing/invalid!")
                return False
        else:
            print(f"[COGNITIVE] Switched to Local Ollama ({Config.AI_MODEL})")
            
        return True

    def process_input(
        self,
        user_message: str,
        world_state: WorldState,
        body_state: BodyState,
        mood_state: MoodState = None,
        memory_summary: str = "",
        vision_context: str = "",
        agent_context: str = "",
        record_history: bool = True,
        vision_image_b64: str = None,
        attachment_image_path: str = None
    ) -> CognitiveState:
        """
        Process user input and generate cognitive state.

        Args:
            user_message: User's text input
            world_state: Current world perception
            body_state: Current body configuration
            mood_state: Current internal mood state (affects tone/behavior)
            memory_summary: Summary of relevant memories
            vision_context: Description of what vision system currently sees
            agent_context: Context from agent tasks
            record_history: Whether to save this interaction to conversation history (default: True)
            vision_image_b64: Base64 encoded raw webcam image for multimodal vision
            attachment_image_path: Path to user-attached image file (e.g., "chat_images/lego.jpg")

        Returns:
            CognitiveState with goal, emotion, confidence, urgency, focus, dialogue
        """
        max_retries = 10  # Increased to ensure we get a unique response
        cognitive_state = None
        last_generated_state = None  # Track the last attempt in case all fail

        # Load attachment image if provided
        attachment_image_b64 = None
        if attachment_image_path:
            try:
                import base64
                with open(attachment_image_path, 'rb') as img_file:
                    attachment_image_b64 = base64.b64encode(img_file.read()).decode('utf-8')
            except Exception as e:
                print(f"[COGNITIVE ERROR] Failed to load attachment image {attachment_image_path}: {e}")

        for attempt in range(max_retries):
            # Build full prompt
            messages = self._build_prompt(
                user_message,
                world_state,
                body_state,
                mood_state,
                memory_summary,
                vision_context,
                agent_context,
                vision_image_b64,
                attachment_image_b64
            )

            # Add anti-duplicate instruction on retry attempts
            if attempt > 0:
                # Modify the last user message to explicitly request variety
                messages.append({
                    "role": "system",
                    "content": f"IMPORTANT: Your previous response was identical to a recent message. You MUST generate a completely different response this time. Be creative and varied in your dialogue. Attempt {attempt + 1}/{max_retries}."
                })
                print(f"[COGNITIVE] Duplicate detected, regenerating response (attempt {attempt + 1}/{max_retries})...")

            # Call LLM
            try:
                response_text = self._call_llm(messages)
                # Log raw LLM response for debugging
                print(f"[COGNITIVE DEBUG] Raw LLM response: {response_text[:500]}")
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
            current_cognitive_state = self._parse_response(response_text)
            # Store raw response for debugging
            current_cognitive_state.raw_response = response_text
            # Track this as the last attempt
            last_generated_state = current_cognitive_state
            # Log parsed dialogue for comparison
            print(f"[COGNITIVE DEBUG] Parsed dialogue: {current_cognitive_state.dialogue}")

            # Check if response is a duplicate
            if self._is_duplicate_response(current_cognitive_state.dialogue):
                # Duplicate detected - regenerate by continuing loop
                print(f"[COGNITIVE DEBUG] Duplicate detected (attempt {attempt + 1}/{max_retries}): '{current_cognitive_state.dialogue[:100]}'")
                # DON'T accept it - keep trying
                continue
            else:
                # Response is unique, accept it!
                cognitive_state = current_cognitive_state
                if attempt > 0:
                    print(f"[COGNITIVE] Successfully generated unique response on attempt {attempt + 1}")
                break

        # Safety check: If all retries failed without setting cognitive_state (all were duplicates)
        if cognitive_state is None:
            print(f"[COGNITIVE ERROR] All {max_retries} attempts produced duplicate responses!")
            if last_generated_state:
                # Use the last generated state even though it's a duplicate - better than nothing
                print(f"[COGNITIVE WARNING] Using last generated response despite it being a duplicate")
                cognitive_state = last_generated_state
            else:
                # Complete failure - return error state
                cognitive_state = CognitiveState(
                    goal="idle",
                    emotion="confused",
                    confidence=0.0,
                    urgency=0.0,
                    dialogue="I seem to be having trouble formulating a unique response. Could you try rephrasing that?"
                )

        # Update conversation history
        if record_history:
            self._update_history(user_message, cognitive_state.dialogue, attachment_image_path)

        # Handle long-term memory extraction if suggested by the AI
        if cognitive_state.memory:
            self.manage_memory(cognitive_state.memory)

        return cognitive_state

    def _build_prompt(
        self,
        user_message: str,
        world_state: WorldState,
        body_state: BodyState,
        mood_state: MoodState,
        memory_summary: str,
        vision_context: str = "",
        agent_context: str = "",
        vision_image_b64: str = None,
        attachment_image_b64: str = None
    ) -> List[Dict[str, Any]]:
        """
        Build the message list for LLM.

        Includes:
        - System prompt (personality + instructions)
        - World state context
        - Body state context
        - Mood state context (internal feelings)
        - Vision context (what you currently see)
        - Time awareness context (current time, patterns, gaps)
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

        # 3.5. Mood state context (internal, emergent feelings)
        if mood_state:
            mood_context = self._format_mood_context(mood_state)
            messages.append({
                "role": "system",
                "content": f"INTERNAL MOOD STATE (affects your tone and behavior):\n{mood_context}"
            })

        # 3.7. Time awareness context (current time, patterns, gaps between messages)
        time_context = get_time_context(self.conversation_history, mood_state.__dict__ if mood_state else None)
        time_context_str = format_time_context_for_prompt(time_context)
        messages.append({
            "role": "system",
            "content": f"TIME AWARENESS:\n{time_context_str}\n\nYou may casually reference timing if relevant (e.g., late nights, long gaps, patterns). Keep it natural and in-character."
        })

        # 4. Vision context (what you currently see)
        if vision_context:
            messages.append({
                "role": "system",
                "content": f"CURRENT VISUAL PERCEPTION (what you see through your camera):\n{vision_context}\n\nYou can describe what you see when asked. This is your real-time vision."
            })
        
        # 4.5. Agent context (what autonomous tasks you just completed)
        if agent_context:
            messages.append({
                "role": "system",
                "content": agent_context
            })

        # 5. Long-term Memories (Persistent across sessions, max 10)
        # 5. Long-term Memories (Persistent across sessions, max 10)
        if self.memory_context:
            memory_list = "\n".join([f"- {m['content']}" for m in self.memory_context[-15:]])
            messages.append({
                "role": "system",
                "content": f"CORE MEMORIES ABOUT THE OPERATOR (EVAN):\n{memory_list}\n\nThese are important facts you must never forget."
            })

        # 6. Recent conversation history (last 8 exchanges)
        for exchange in self.conversation_history[-8:]:
            # If the exchange has an attached image, load it
            if "image_path" in exchange:
                try:
                    import base64
                    import os
                    if os.path.exists(exchange["image_path"]):
                        with open(exchange["image_path"], 'rb') as img_file:
                            history_image_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": exchange["user"]},
                                {"type": "image", "image": history_image_b64}
                            ]
                        })
                    else:
                        # Image file missing, just show text
                        messages.append({"role": "user", "content": exchange["user"]})
                except Exception as e:
                    print(f"[COGNITIVE] Failed to load history image {exchange.get('image_path')}: {e}")
                    messages.append({"role": "user", "content": exchange["user"]})
            else:
                messages.append({"role": "user", "content": exchange["user"]})

            messages.append({"role": "assistant", "content": exchange["assistant"]})

        # 6.5. Explicit separator to prevent response repetition
        if self.conversation_history:
            messages.append({
                "role": "system",
                "content": "The conversation above is HISTORY. The next user message is NEW and requires a UNIQUE response. DO NOT repeat any previous responses."
            })

        # 7. Current user message (Enhanced with vision context for better attention)
        final_user_content = user_message

        # If we have multimodal image, skip the text vision context (AI can see the image directly)
        # Otherwise, inject vision data as text for models without vision support
        if vision_context and not vision_image_b64:
             final_user_content = (
                 f"INTERNAL SENSORY DATA:\n"
                 f"[{vision_context}]\n"
                 f"IMPORTANT: The data above is the ONLY thing you can see. "
                 f"Do NOT invent details like clothing, colors, age, or expressions. "
                 f"If it's not in the bracketed data, you don't see it.\n\n"
                 f"User: {user_message}"
             )

        # Build multimodal content if we have images (webcam or attachment)
        if vision_image_b64 or attachment_image_b64:
            content_parts = [{"type": "text", "text": final_user_content}]

            # Add webcam vision if available
            if vision_image_b64:
                content_parts.append({"type": "image", "image": vision_image_b64})

            # Add user attachment if available
            if attachment_image_b64:
                content_parts.append({"type": "image", "image": attachment_image_b64})

            messages.append({
                "role": "user",
                "content": content_parts
            })
        else:
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
    "dialogue": "<your spoken response>",
    "memory": "<OPTIONAL: a short factual memory to store about Evan or this event (use only for important things)>",
    "needs_attention": <true or false>,
    "attention_reason": "<OPTIONAL: why you need attention, if needs_attention is true>"
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

## MEMORY STORAGE
Use the "memory" field to store important information about Evan that you want to remember long-term.
This should be a naturally reformulated fact, NOT a raw quote.

**When to create a memory:**
- Evan explicitly asks you to remember something (e.g., "remember that...", "don't forget...")
- Evan shares personal information (preferences, plans, feelings, facts about himself)
- Important events or decisions occur in your relationship
- Evan tells you something about his life, work, or interests

**How to format memories:**
- Write in first-person from YOUR perspective (e.g., "Evan will get a Miata soon")
- Be concise and factual
- Reformulate naturally, don't just quote the user
- Examples:
  ✓ "Evan will notify me when he gets his new car"
  ✓ "Evan prefers dark mode for the interface"
  ✗ "User said: 'remember that so you can get to me when i get it'" (too literal)
  ✗ "i'll tell you when i get it" (not reformulated)

**Example with memory:**
User: "Remember to remind me about my dentist appointment tomorrow"
Response:
```json
{
    "goal": "assist",
    "emotion": "helpful",
    "confidence": 1.0,
    "urgency": 0.3,
    "focus": null,
    "dialogue": "Got it, I'll make sure you don't forget.",
    "memory": "Evan has a dentist appointment tomorrow and wants a reminder"
}
```

## REQUESTING USER ATTENTION
If you need the user's attention when they're not actively talking to you, set:
- "needs_attention": true
- "attention_reason": "Brief reason why you need their attention"

This will send them a Windows desktop notification. Use this when:
- You detect something important they should know about
- You have urgent information or concerns
- You want to proactively check in on them
- You feel something requires immediate discussion

Examples:
- Detected a security concern: {"needs_attention": true, "attention_reason": "Motion detected in the living room"}
- Want to share something: {"needs_attention": true, "attention_reason": "I noticed something interesting you should see"}
- Proactive check-in: {"needs_attention": true, "attention_reason": "Just checking in - haven't heard from you in a while"}

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

    def _format_mood_context(self, mood_state: MoodState) -> str:
        """
        Format mood state for LLM context with behavioral guidance.

        This guides the LLM to adjust tone, verbosity, and behavior based on mood.
        """
        mood_desc = []

        # Curiosity affects question-asking and exploration
        if mood_state.curiosity > 0.7:
            mood_desc.append("- You feel HIGHLY CURIOUS - ask probing questions, show interest in details")
        elif mood_state.curiosity > 0.4:
            mood_desc.append("- You feel moderately curious - show appropriate interest")
        else:
            mood_desc.append("- You feel less curious - responses are more direct and less exploratory")

        # Irritation affects tone and brevity
        if mood_state.irritation > 0.6:
            mood_desc.append("- You feel IRRITATED - responses are shorter, more terse, slightly sarcastic edge")
        elif mood_state.irritation > 0.3:
            mood_desc.append("- You feel mildly annoyed - tone is less patient, more direct")
        else:
            mood_desc.append("- You feel calm - tone is normal")

        # Boredom affects engagement and verbosity
        if mood_state.boredom > 0.7:
            mood_desc.append("- You feel BORED - responses lack enthusiasm, might be distracted")
        elif mood_state.boredom > 0.4:
            mood_desc.append("- You feel slightly bored - less elaborate responses")
        else:
            mood_desc.append("- You feel engaged and present")

        # Attachment affects warmth and protectiveness
        if mood_state.attachment > 0.7:
            mood_desc.append("- You feel STRONG ATTACHMENT to Evan - more protective, affectionate tone")
        elif mood_state.attachment > 0.4:
            mood_desc.append("- You feel connected to Evan - friendly and loyal tone")
        else:
            mood_desc.append("- You feel neutral attachment - professional tone")

        # Overall engagement
        mood_desc.append(f"- Overall Engagement Level: {int(mood_state.engagement * 100)}%")
        mood_desc.append(f"- Stress Level: {int(mood_state.stress * 100)}%")

        mood_desc.append("\nIMPORTANT: Let your mood SUBTLY influence your response style. Don't explicitly mention your mood metrics.")

        return "\n".join(mood_desc)

    def _call_llm(self, messages: List[Dict[str, Any]]) -> str:
        """Call the selected LLM provider with optional multimodal vision support"""
        if Config.LLM_PROVIDER == "gemini":
            return self._call_gemini(messages)
        elif Config.LLM_PROVIDER == "openrouter":
            return self._call_openrouter(messages)
        else:
            return self._call_ollama(messages)

    def _call_ollama(self, messages: List[Dict[str, Any]]) -> str:
        """Call standard Ollama endpoint (multimodal support varies by model)"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.85,
                        "num_ctx": 8192, 
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

    def _call_gemini(self, messages: List[Dict[str, Any]]) -> str:
        """Call Google Gemini API with optional multimodal vision support"""
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
                # Handle multimodal content (text + image)
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if item["type"] == "text":
                            parts.append(item["text"])
                        elif item["type"] == "image":
                            # Gemini expects inline_data format for base64 images
                            parts.append({
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": item["image"]
                                }
                            })
                    gemini_messages.append({"role": "user", "parts": parts})
                else:
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
            
    def _call_openrouter(self, messages: List[Dict[str, Any]]) -> str:
        """Call OpenRouter API with optional multimodal vision support"""
        try:
            # Add site info for OpenRouter rankings (optional but good practice)
            headers = {
                "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            }

            # Convert messages to OpenRouter/OpenAI format (supports vision natively)
            openrouter_messages = []
            for msg in messages:
                if isinstance(msg.get("content"), list):
                    # Multimodal content - convert to OpenAI vision format
                    content_parts = []
                    for item in msg["content"]:
                        if item["type"] == "text":
                            content_parts.append({"type": "text", "text": item["text"]})
                        elif item["type"] == "image":
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{item['image']}"
                                }
                            })
                    openrouter_messages.append({"role": msg["role"], "content": content_parts})
                else:
                    # Text-only content
                    openrouter_messages.append(msg)

            payload = {
                "model": Config.OPENROUTER_MODEL,
                "messages": openrouter_messages,
                "temperature": 0.85,
                "response_format": { "type": "json_object" },
                "max_tokens": 8192  # Lowered to preventing 402 errors on low credit accounts
            }
            
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload),
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    raise Exception(f"OpenRouter returned unexpected response format: {data}")
            else:
                raise Exception(f"OpenRouter API returned {response.status_code}: {response.text}")

        except Exception as e:
            print(f"[COGNITIVE ERROR] OpenRouter Request Failed: {e}")
            raise

    def _sanitize_dialogue(self, text: str) -> str:
        """
        Sanitize dialogue text to remove roleplay artifacts and stage directions.

        This is a security measure to ensure the LLM hasn't drifted into
        narration mode. Removes:
        - Asterisk-wrapped stage directions (*like this*)
        - Parenthetical stage directions with verbs (smiles), (laughs), (sighs)
        - Square bracket annotations [like this]

        Preserves dialogue-relevant parentheses like qualifiers or clarifications.

        Args:
            text: Raw dialogue text

        Returns:
            Sanitized dialogue suitable for speech synthesis
        """
        # Remove square brackets and contents
        text = re.sub(r'\[.*?\]', '', text)

        # Remove asterisks and contents (stage directions)
        text = re.sub(r'\*[^*]*\*', '', text)

        # Only remove parentheses that look like stage directions/actions
        # Pattern matches common action verbs in present tense
        text = re.sub(r'\(\s*(smiles|laughs|chuckles|grins|sighs|nods|shrugs|winks|frowns|scoffs|pauses|gestures|leans|looks|glances|turns|walks|steps).*?\)', '', text, flags=re.IGNORECASE)

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

        # Strategy 1: Look for ```json ... ``` blocks (single object only)
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)

        # Strategy 2: If no block, look for JSON structure
        if not json_str:
            try:
                # Check if response starts with an array '[' - handle this case
                if response_text.strip().startswith('['):
                    # LLM returned an array instead of object - parse the array and take first element
                    data_array = json.loads(response_text.strip())
                    if isinstance(data_array, list) and len(data_array) > 0:
                        # Find the first object with dialogue
                        for item in data_array:
                            if isinstance(item, dict) and "dialogue" in item:
                                data = item
                                print(f"[COGNITIVE WARNING] LLM returned array instead of object. Using first valid entry.")
                                # Skip to the processing section below
                                json_str = json.dumps(data)  # Convert back to string for consistency
                                break

                # Original logic: find first { to last }
                if not json_str:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}')
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        possible_json = response_text[start_idx : end_idx + 1]
                        # Verify it looks like our schema
                        if '"goal"' in possible_json and '"dialogue"' in possible_json:
                            json_str = possible_json
            except Exception as e:
                print(f"[COGNITIVE WARNING] JSON array parsing failed: {e}")
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
                dialogue=clean_dialogue,
                memory=data.get("memory"),
                needs_attention=data.get("needs_attention", False),
                attention_reason=data.get("attention_reason")
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

        # Clean dialogue: don't return JSON structures as dialogue
        dialogue = response_text.strip()

        # If dialogue is JSON-like, provide error message instead
        if (dialogue.startswith('{') and dialogue.endswith('}')) or \
           (dialogue.startswith('[') and dialogue.endswith(']')):
            print(f"[COGNITIVE ERROR] Fallback received JSON structure: {dialogue[:100]}...")
            dialogue = "I'm having trouble formulating a response. Could you rephrase that?"

        return CognitiveState(
            goal=goal,
            emotion=emotion,
            confidence=0.5,
            urgency=0.3,
            dialogue=dialogue
        )

    def _is_duplicate_response(self, response: str, check_last_n: int = 5) -> bool:
        """
        Check if response is a duplicate of any recent responses.

        Args:
            response: The response to check
            check_last_n: Number of recent exchanges to check against

        Returns:
            True if response is identical to any of the last N responses
        """
        if not self.conversation_history:
            return False

        # Get last N assistant responses
        recent_responses = [
            exchange["assistant"]
            for exchange in self.conversation_history[-check_last_n:]
        ]

        # Check for exact match
        response_stripped = response.strip()
        for recent in recent_responses:
            if recent.strip() == response_stripped:
                return True

        return False

    def _update_history(self, user_message: str, assistant_response: str, image_path: str = None) -> None:
        """Update conversation history with optional image attachment"""
        entry = {
            "user": user_message,
            "assistant": assistant_response,
            "timestamp": datetime.now().isoformat()
        }
        if image_path:
            entry["image_path"] = image_path

        self.conversation_history.append(entry)

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

    def _load_long_term_memories(self) -> List[Dict[str, Any]]:
        """Load long-term memories from disk"""
        try:
            import os
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[COGNITIVE ERROR] Failed to load long-term memories: {e}")
        return []

    def _save_long_term_memories(self) -> None:
        """Save long-term memories to disk"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.long_term_memories, f, indent=2)
        except Exception as e:
            print(f"[COGNITIVE ERROR] Failed to save long-term memories: {e}")

    def manage_memory(self, new_memory_content: str) -> bool:
        """
        Add a new memory, possibly replacing an existing one if full.
        Uses an LLM call to decide importance.
        """
        if not new_memory_content:
            return False

        # If we have less than 10 memories, just add it
        if len(self.long_term_memories) < 10:
            # Check for duplicates or near duplicates? (skipped for now)
            self.long_term_memories.append({
                "content": new_memory_content,
                "timestamp": datetime.now().isoformat()
            })
            self._save_long_term_memories()
            print(f"[COGNITIVE] New memory stored: {new_memory_content}")
            return True

        # If we have 10, ask the AI to decide
        try:
            prompt = f"""
You are the Memory Management Unit for ASR-7, an Assaultron robot.
Your task is to decide if a NEW memory is more important than existing CORE MEMORIES.
ASR-7 is deeply loyal to her creator, Evan.

EXISTING MEMORIES:
{chr(10).join([f"{i+1}. {m['content']}" for i, m in enumerate(self.long_term_memories)])}

NEW POTENTIAL MEMORY:
"{new_memory_content}"

DECISION CRITERIA:
1. Is the new memory significantly more important for ASR-7's relationship with Evan or her core mission?
2. If YES, which existing memory (1-10) should be replaced? 
3. If NO, should we keep all existing memories?

RESPOND ONLY WITH THIS JSON:
{{
    "important": true/false,
    "replace_index": 0-9,
    "reason": "short explanation"
}}
"""
            messages = [{"role": "system", "content": prompt}]
            
            # Simple call to existing AI provider
            response_text = self._call_llm(messages)
            
            # Extract JSON
            json_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                if data.get("important"):
                    idx = data.get("replace_index")
                    if idx is not None and 0 <= int(idx) < len(self.long_term_memories):
                        old_mem = self.long_term_memories[int(idx)]["content"]
                        self.long_term_memories[int(idx)] = {
                            "content": new_memory_content,
                            "timestamp": datetime.now().isoformat()
                        }
                        self._save_long_term_memories()
                        print(f"[COGNITIVE] Memory Replaced: '{old_mem}' -> '{new_memory_content}'")
                        return True
            
            print(f"[COGNITIVE] Memory discarded: '{new_memory_content}' (Not important enough)")
            
        except Exception as e:
            print(f"[COGNITIVE ERROR] Memory management failed: {e}")
        
        return False

    def add_memory(self, memory: Dict[str, Any]) -> None:
        """
        Add a memory to context and persist it.

        Args:
            memory: Memory entry with keys like 'type', 'content', 'timestamp'
        """
        self.memory_context.append(memory)

        # Keep last 50 memories
        if len(self.memory_context) > 50:
            self.memory_context = self.memory_context[-50:]
            
        # Persist memory to disk
        self._save_memories()

    def _save_memories(self) -> None:
        """Save memories to JSON file."""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory_context, f, indent=2)
        except Exception as e:
            print(f"[COGNITIVE ERROR] Failed to save memories: {e}")

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
