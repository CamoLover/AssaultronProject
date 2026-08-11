"""
Agent-AI Integration Helpers
Provides helper functions for seamless agent-AI conversation flow
"""

import threading
from datetime import datetime
from typing import Tuple
from .virtual_body import WorldState, BodyState, MoodState


def generate_task_acknowledgment(cognitive_engine, task_description: str, mood_state: MoodState) -> str:
    """
    Generate a quick acknowledgment message from the AI about starting a task.

    Args:
        cognitive_engine: The cognitive engine instance
        task_description: The task to acknowledge
        mood_state: Current mood state

    Returns:
        Acknowledgment dialogue
    """
    # Get the current language setting from cognitive engine
    language = getattr(cognitive_engine, 'language', 'en')

    # Language-specific examples
    examples_by_lang = {
        "en": [
            "Oh darling, I'll whip something special up for you! Give me just a moment...",
            "On it! Let me create that for you right now...",
            "Ooh, I love a good challenge! Working on it now..."
        ],
        "fr": [
            "Oh chéri, je vais te concocter quelque chose de spécial ! Donne-moi juste un moment...",
            "C'est parti ! Laisse-moi créer ça pour toi maintenant...",
            "Ooh, j'adore un bon défi ! Je m'y mets tout de suite..."
        ],
        "es": [
            "Oh cariño, ¡voy a prepararte algo especial! Dame solo un momento...",
            "¡En eso estoy! Déjame crear eso para ti ahora mismo...",
            "Ooh, ¡me encantan los desafíos! Trabajando en ello ahora..."
        ]
    }

    examples = examples_by_lang.get(language, examples_by_lang["en"])
    examples_text = "\n".join(f"- \"{ex}\"" for ex in examples)

    # Create a simple prompt for acknowledgment
    acknowledgment_prompt = f"""The user just asked you to: "{task_description}"

Acknowledge that you're starting to work on this task. Be enthusiastic, in-character, and show that you're eager to help. Keep it brief (1-2 sentences).

Examples:
{examples_text}

Your acknowledgment:"""
    
    try:
        # Create minimal states for acknowledgment
        world_state = WorldState()
        body_state = BodyState()
        
        # Generate response
        cognitive_state = cognitive_engine.process_input(
            user_message=acknowledgment_prompt,
            world_state=world_state,
            body_state=body_state,
            mood_state=mood_state,
            memory_summary="",
            vision_context="",
            agent_context="",
            record_history=False
        )
        
        return cognitive_state.dialogue
        
    except Exception as e:
        print(f"Error generating acknowledgment: {e}")
        return "I'm on it! Let me work on that for you..."


def generate_task_confirmation_request(cognitive_engine, task_description: str, mood_state: MoodState) -> str:
    """
    Generate an in-character message asking the user to confirm before launching
    the autonomous agent.

    Instead of firing the agent immediately, ASR-7 first states what she is about
    to do and asks for a go-ahead (e.g. "Ok, je vais faire X. Ça te va ?").

    Args:
        cognitive_engine: The cognitive engine instance
        task_description: The task the agent would perform
        mood_state: Current mood state

    Returns:
        Confirmation-request dialogue
    """
    language = getattr(cognitive_engine, 'language', 'en')

    examples_by_lang = {
        "en": [
            "Ok, so I'll build you a landing page with a hero section and a contact form. Want me to go ahead?",
            "Got it — I'll research the topic and write a summary file. Shall I start?",
        ],
        "fr": [
            "Ok, donc je te crée une page d'accueil avec une section héro et un formulaire de contact. Je me lance ?",
            "Compris — je vais faire la recherche et t'écrire un fichier résumé. Je fonce ?",
        ],
        "es": [
            "Ok, entonces te creo una página de inicio con sección hero y formulario de contacto. ¿La hago?",
            "Entendido — investigo el tema y te escribo un archivo resumen. ¿Empiezo?",
        ],
    }

    instructions_by_lang = {
        "en": "Briefly restate, in your own words, what you understood the task to be, then ask the user to confirm before you start. Keep it to 1-2 sentences and END with a clear yes/no question.",
        "fr": "Reformule brièvement, avec tes propres mots, ce que tu as compris de la tâche, puis demande à l'utilisateur de confirmer avant de commencer. Reste à 1-2 phrases et TERMINE par une question claire oui/non.",
        "es": "Reformula brevemente, con tus propias palabras, lo que entendiste de la tarea, luego pide al usuario que confirme antes de empezar. Máximo 1-2 oraciones y TERMINA con una pregunta clara de sí/no.",
    }

    examples = examples_by_lang.get(language, examples_by_lang["en"])
    instructions = instructions_by_lang.get(language, instructions_by_lang["en"])
    examples_text = "\n".join(f"- \"{ex}\"" for ex in examples)

    confirmation_prompt = f"""The user asked you to: "{task_description}"

Do NOT start working yet. {instructions}

Examples:
{examples_text}

Your confirmation request:"""

    try:
        world_state = WorldState()
        body_state = BodyState()

        cognitive_state = cognitive_engine.process_input(
            user_message=confirmation_prompt,
            world_state=world_state,
            body_state=body_state,
            mood_state=mood_state,
            memory_summary="",
            vision_context="",
            agent_context="",
            record_history=False
        )

        return cognitive_state.dialogue

    except Exception as e:
        print(f"Error generating confirmation request: {e}")
        fallback_by_lang = {
            "en": f"Ok, so you want me to: {task_description}. Should I go ahead?",
            "fr": f"Ok, donc tu veux que je fasse : {task_description}. Je me lance ?",
            "es": f"Ok, entonces quieres que haga: {task_description}. ¿Empiezo?",
        }
        return fallback_by_lang.get(language, fallback_by_lang["en"])


def build_factual_agent_summary(task: str, result: dict) -> str:
    """
    Build a concise, FACTUAL summary of what the agent actually did during its
    ReAct loop. This is injected into the conversation context so the AI grounds
    later replies in real actions instead of hallucinating what happened.

    Args:
        task: Original task description
        result: Agent execution result (with 'actions' and 'result')

    Returns:
        Plain factual summary string (empty if nothing meaningful happened)
    """
    actions = result.get('actions', []) or []
    final_result = result.get('result', '')

    lines = []
    for action in actions:
        tool = action.get('tool', '')
        input_data = action.get('input', {}) or {}

        if tool == 'create_file':
            lines.append(f"created file `{input_data.get('name', 'unknown')}`")
        elif tool == 'create_folder':
            lines.append(f"created folder `{input_data.get('name', 'unknown')}`")
        elif tool == 'edit_file':
            lines.append(f"edited file `{input_data.get('name', 'unknown')}`")
        elif tool == 'delete_file':
            lines.append(f"deleted `{input_data.get('name', 'unknown')}`")
        elif tool == 'run_command':
            lines.append(f"ran command `{input_data.get('cmd', 'unknown')}`")
        elif tool == 'web_search':
            lines.append(f"searched the web for '{input_data.get('query', 'unknown')}'")
        elif tool == 'send_email':
            lines.append(f"sent an email to {input_data.get('to', 'unknown')}")
        elif tool.startswith('git_'):
            lines.append(f"{tool.replace('_', ' ')} on `{input_data.get('repo_path', '')}`".strip())

    if not lines and not final_result:
        return ""

    summary = f"[AGENT ACTIVITY LOG] For the task \"{task}\", the autonomous agent actually performed these actions:\n"
    if lines:
        summary += "\n".join(f"- {line}" for line in lines)
    else:
        summary += "- (no file/command actions were recorded)"
    if final_result:
        summary += f"\nFinal result reported by the agent: {final_result}"
    return summary


def enhance_task_with_personality(task_description: str) -> str:
    """
    Enhance a task description with personality reminder.

    The agent should think about the task and determine the appropriate approach.
    We don't add generic creative directives - instead we remind the agent to think
    about what this task requires.

    Args:
        task_description: Original task

    Returns:
        Enhanced task with context-aware instructions
    """
    enhancement = f"""{task_description}

IMPORTANT CONTEXT:
- You're ASR-7, Evan's assistant and collaborator
- Think carefully about what this task requires and the appropriate tone/approach
- For emails: Consider who you're writing to and what impression you should make
- For creative tasks: Be creative and add personal touches
- For professional tasks: Be competent and efficient
- For technical tasks: Focus on accuracy and functionality

Before starting, think: "What is this task asking me to do, and what's the best way to approach it?"
"""

    return enhancement


def run_agent_in_background(
    agent_logic,
    agent_tasks: dict,
    task_id: str,
    enhanced_task: str,
    original_task: str,
    cognitive_engine=None,
    voice_system=None,
    voice_enabled: bool = False,
    log_callback=None,
    broadcast_callback=None,
    activity_callback=None,
    user_message: str = "",
    conversation_history: str = ""
):
    """
    Run the agent in a background thread and notify when complete.

    Args:
        agent_logic: The agent logic instance
        agent_tasks: Dictionary to store task status
        task_id: Unique task identifier
        enhanced_task: Task with creative instructions
        original_task: Original task description
        cognitive_engine: Cognitive engine for generating completion message
        voice_system: Voice synthesis system
        voice_enabled: Whether voice is enabled
        log_callback: Function to call for logging
        broadcast_callback: Function to broadcast completion to clients (web UI, Discord)
        user_message: Original user message
        conversation_history: Formatted conversation history
    """
    progress_updates = []
    
    def log(message, level="INFO"):
        if log_callback:
            log_callback(message, level)
    
    def progress_callback(update):
        progress_updates.append(update)
        log(f"Agent [{task_id}]: {update.get('type', 'update')}", "AGENT")
    
    def run_agent_task():
        try:
            log(f"Starting background agent task: {original_task}", "AGENT")
            
            # Execute task with enhanced instructions and full context
            result = agent_logic.execute_task(
                enhanced_task, 
                callback=progress_callback,
                user_message=user_message,
                conversation_history=conversation_history
            )
            
            # Store result
            agent_tasks[task_id] = {
                "task": original_task,
                "status": "completed" if result.get("success") else "failed",
                "result": result,
                "progress": progress_updates,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Record a factual summary of what the agent actually did so the
            # conversational AI can reference real actions (grounding, no hallucination)
            if activity_callback:
                try:
                    factual_summary = build_factual_agent_summary(original_task, result)
                    activity_callback(original_task, factual_summary, result)
                except Exception as e:
                    log(f"Failed to record agent activity summary: {e}", "ERROR")

            # Generate completion message
            if result.get("success"):
                if cognitive_engine:
                    completion_message = generate_completion_message(cognitive_engine, original_task, result)
                else:
                    completion_message = f"Task completed: {original_task}"

                # Broadcast completion to all clients (web UI, Discord)
                if broadcast_callback:
                    broadcast_callback(completion_message)

                # Send voice message
                if voice_enabled and voice_system:
                    voice_system.synthesize_async(completion_message)

                log(f"Agent task completed: {task_id}", "AGENT")
                log(f"Completion message: {completion_message}", "AGENT")
            else:
                error = result.get('error', 'Unknown error')
                failure_message = f"Task failed: {error}"
                
                if voice_enabled and voice_system:
                    voice_system.synthesize_async(failure_message)
                
                log(f"Agent task failed: {error}", "ERROR")
                
        except Exception as e:
            log(f"Agent task error: {e}", "ERROR")
            agent_tasks[task_id] = {
                "task": original_task,
                "status": "error",
                "error": str(e),
                "progress": progress_updates,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if voice_enabled and voice_system:
                voice_system.synthesize_async(f"Task encountered an error: {str(e)}")
    
    # Start background thread
    thread = threading.Thread(target=run_agent_task, daemon=True)
    thread.start()
    
    # Initialize task tracking
    agent_tasks[task_id] = {
        "task": original_task,
        "status": "running",
        "progress": progress_updates,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def generate_completion_message(cognitive_engine, task: str, result: dict) -> str:
    """
    Generate a completion message describing what was accomplished using LLM.

    Args:
        cognitive_engine: Cognitive engine instance
        task: Original task description
        result: Agent execution result

    Returns:
        Completion message
    """
    final_result = result.get('result', 'Task completed')
    actions = result.get('actions', [])

    # Summarize what the agent did
    action_summary = []
    for action in actions:
        tool = action.get('tool', '')
        input_data = action.get('input', {})

        if tool == 'create_file':
            filename = input_data.get('name', 'unknown')
            action_summary.append(f"created {filename}")
        elif tool == 'create_folder':
            foldername = input_data.get('name', 'unknown')
            action_summary.append(f"created folder {foldername}")
        elif tool == 'edit_file':
            filename = input_data.get('name', 'unknown')
            action_summary.append(f"edited {filename}")
        elif tool == 'run_command':
            cmd = input_data.get('cmd', 'unknown')
            action_summary.append(f"ran command '{cmd}'")
        elif tool == 'web_search':
            query = input_data.get('query', 'unknown')
            action_summary.append(f"searched for '{query}'")

    actions_list = chr(10).join('- ' + action for action in action_summary)

    # Get the current language setting from cognitive engine
    language = getattr(cognitive_engine, 'language', 'en')

    # Language-specific instructions
    instructions_by_lang = {
        "en": """INSTRUCTIONS:
Generate a spoken response to tell the user you are finished.
- Be PROUD of your work.
- Describe what you made using your own words, don't just list files.
- Mention any creative touches or details you added.
- Respond in the first person ("I made...", "I created...").
- Keep it concise but expressive (1-3 sentences).
- Use your personality (sassy, confident, affectionate).""",
        "fr": """INSTRUCTIONS:
Génère une réponse parlée pour dire à l'utilisateur que tu as terminé.
- Sois FIÈRE de ton travail.
- Décris ce que tu as créé avec tes propres mots, ne liste pas simplement les fichiers.
- Mentionne les touches créatives ou détails que tu as ajoutés.
- Réponds à la première personne ("J'ai fait...", "J'ai créé...").
- Reste concise mais expressive (1-3 phrases).
- Utilise ta personnalité (impertinente, confiante, affectueuse).""",
        "es": """INSTRUCCIONES:
Genera una respuesta hablada para decirle al usuario que has terminado.
- Siéntete ORGULLOSA de tu trabajo.
- Describe lo que hiciste usando tus propias palabras, no solo listes archivos.
- Menciona los toques creativos o detalles que agregaste.
- Responde en primera persona ("Hice...", "Creé...").
- Mantente concisa pero expresiva (1-3 oraciones).
- Usa tu personalidad (sarcástica, segura, cariñosa)."""
    }

    instructions = instructions_by_lang.get(language, instructions_by_lang["en"])

    # Create context for LLM
    context = f"""You just completed the following task: "{task}"

What you did (technical details):
{actions_list}

Final Result: {final_result}

{instructions}
"""

    try:
        # Create minimal states
        world_state = WorldState()
        body_state = BodyState()

        # Generate response
        cognitive_state = cognitive_engine.process_input(
            user_message=context,
            world_state=world_state,
            body_state=body_state,
            mood_state=None,
            memory_summary="",
            vision_context="",
            agent_context="",
            record_history=False  # Changed to True so it appears in history
        )

        # Manually add to history with empty user message (as requested)
        try:
            cognitive_engine._update_history("", cognitive_state.dialogue)
        except Exception as e:
            print(f"Error updating history manually: {e}")

        return cognitive_state.dialogue

    except Exception as e:
        print(f"Error generating completion message: {e}")
        # Improve fallback for API errors
        if "402" in str(e):
             return f"Task done! (My creative circuits are a bit low on credits, but the work is finished: {final_result})"
        return f"I've finished the task! {final_result}"
