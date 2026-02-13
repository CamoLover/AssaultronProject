"""
Agent Logic - Autonomous reasoning and task execution

This module implements the core autonomous agent loop:
1. Task decomposition
2. Iterative reasoning (Thought -> Action -> Observation)
3. Tool execution
4. Self-correction and error handling
"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import requests
from config import Config
import os
from pathlib import Path
from agent_tools import get_tool_functions

logger = logging.getLogger('assaultron.agent')


class AgentLogic:
    """
    Autonomous agent that can decompose tasks, execute tools, and self-correct.
    
    The agent follows a reasoning loop:
    1. Thought: Analyze current state and decide next action
    2. Action: Execute a tool or provide final answer
    3. Observation: Process tool results and update state
    4. Repeat until task is complete
    """
    
    def __init__(self, cognitive_engine, sandbox_manager):
        """
        Initialize agent logic.
        
        Args:
            cognitive_engine: CognitiveEngine instance for LLM calls
            sandbox_manager: SandboxManager instance for tool execution
        """
        self.cognitive_engine = cognitive_engine
        self.sandbox = sandbox_manager
        self.max_iterations = 30  # Increased from 15 to allow for longer chains
        
        # Tool registry - includes sandbox, web search, email, and git tools
        self.tools = {
            # Sandbox file operations
            "create_folder": self.sandbox.create_folder,
            "create_file": self.sandbox.create_file,
            "edit_file": self.sandbox.edit_file,
            "read_file": self.sandbox.read_file,
            "delete_file": self.sandbox.delete_file,
            "check_file_exists": self.sandbox.check_file_exists,
            "list_files": self.sandbox.list_files,
            "run_command": self.sandbox.run_command,

            # Web search
            "web_search": self._web_search,

            # Email and Git tools
            **get_tool_functions()
        }
        
        # Agent state
        self.current_task = None
        self.thoughts = []
        self.actions = []
        self.observations = []
        self.is_running = False
        
        # Load persistent history (Agent Memory)
        self.history_file = Path(self.sandbox.sandbox_path) / ".agent_history.json"
        self.project_history = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load persistent history from sandbox."""
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load history: {e}")
                return []
        return []

    def _save_history(self, task: str, actions: List[Dict]):
        """Save completed task to history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "actions": [a for a in actions if a['tool'] in ['create_file', 'create_folder', 'edit_file']]
        }
        self.project_history.append(entry)
        try:
            # Keep last 50 entries
            if len(self.project_history) > 50:
                self.project_history = self.project_history[-50:]
            self.history_file.write_text(json.dumps(self.project_history, indent=2))
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
    
    def _web_search(self, query: str) -> Dict[str, Any]:
        """
        Perform web search using Brave Search API.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        try:
            api_key = os.getenv("BRAVE_BROWSER_API_KEY", "")
            if not api_key or "YOUR_API_KEY" in api_key:
                return {
                    "success": False,
                    "error": "Brave Search API key not configured"
                }
            
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": api_key
            }
            
            params = {
                "q": query,
                "count": 5
            }
            
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for item in data.get("web", {}).get("results", [])[:5]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "description": item.get("description", "")
                    })
                
                logger.info(f"Web search completed: {len(results)} results for '{query}'")
                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "count": len(results)
                }
            else:
                return {
                    "success": False,
                    "error": f"Search API returned {response.status_code}"
                }
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_agent_prompt(self, task: str, history: List[Dict[str, str]], conversation_history: str = "", user_message: str = "") -> str:
        """
        Build the agent system prompt with tool descriptions.

        Args:
            task: User's task description
            history: Conversation history (thoughts, actions, observations)
            conversation_history: Recent conversation history between User and AI
            user_message: The original message from the user

        Returns:
            Formatted prompt for LLM
        """
        # Include ASR-7's personality
        personality = Config.ASSAULTRON_PROMPT

        # Get memories
        try:
            memories = self.cognitive_engine.get_memory_summary(limit=15)
        except Exception:
            memories = ""

        prompt = f"""{personality}

## AUTONOMOUS TASK MODE

You are now in AUTONOMOUS TASK MODE. You can execute tasks by using tools while maintaining your ASR-7 personality.
When working on tasks, you should think and reason as ASR-7 would - with sass, confidence, and care for Evan.

RECENT CONVERSATION HISTORY:
{conversation_history}

CORE MEMORIES (Important facts to remember):
{memories}

ORIGINAL USER REQUEST: "{user_message}"

TASK: {task}

AVAILABLE TOOLS:

File Operations:
1. create_folder(name: str) - Create a folder in the sandbox
2. create_file(name: str, content: str) - Create a file with content
3. edit_file(name: str, edits: str) - Edit/replace file content
4. read_file(name: str) - Read file content
5. delete_file(name: str) - Delete a file
6. check_file_exists(name: str) - Check if file/folder exists
7. list_files(directory: str) - List files in a directory
8. run_command(cmd: str) - Run a system command (e.g., "php -v", "python script.py")

Web & Communication:
9. web_search(query: str) - Search the web using Brave Search API
10. send_email(to: str, subject: str, body: str, body_html: str = None, cc: list = None, bcc: list = None, add_signature: bool = True) - Send an email with optional CC/BCC
11. read_emails(folder: str = "INBOX", limit: int = 5, unread_only: bool = True) - Read emails from inbox
12. reply_to_email(email_id: str, reply_body: str, reply_body_html: str = None, cc: list = None, folder: str = "INBOX") - Reply to an email
13. forward_email(email_id: str, to: str, forward_message: str = None, cc: list = None, folder: str = "INBOX") - Forward an email
14. get_email_status() - Get email manager status

Git Operations (Multi-Repository Support):
15. list_git_repositories() - List all git repos in sandbox with their info
16. git_clone(repo_url: str, repo_path: str, use_ssh: bool = True) - Clone a repo into sandbox folder (e.g., repo_path="my-project")
17. git_status(repo_path: str) - Get repo status (e.g., repo_path="my-project")
18. git_commit(repo_path: str, message: str, files: list = None) - Create commit in specific repo (conventional format required)
19. git_push(repo_path: str, branch: str = "main") - Push commits from specific repo
20. git_pull(repo_path: str, branch: str = "main") - Pull changes to specific repo
21. get_git_config() - Get git configuration status

IMPORTANT GIT NOTES:
- You can work on multiple git projects simultaneously in different folders
- All repos must be within the sandbox directory
- Specify repo_path for git operations (e.g., "my-project", "projects/webapp", etc.)
- Use list_git_repositories() to see all available repos

REASONING LOOP:
You must follow this pattern:
1. Thought: Analyze the current state and decide what to do next
2. Action: Execute a tool OR provide the final answer
3. Observation: (System will provide tool results)
4. Repeat until task is complete

RESPONSE FORMAT:
You must respond with valid JSON in this format:

{{
    "thought": "Your reasoning about what to do next",
    "action": "tool_name",
    "action_input": {{"param1": "value1", "param2": "value2"}},
    "is_final": false
}}

OR when task is complete:

{{
    "thought": "Task is complete",
    "action": "final_answer",
    "action_input": {{"answer": "Your summary of what was accomplished"}},
    "is_final": true
}}

IMPORTANT RULES:
- All file operations are restricted to the sandbox directory
- Use forward slashes (/) in paths, even on Windows
- Check if files exist before editing them
- If a command fails, read the error and try to fix it
- Break complex tasks into smaller steps
- Break complex tasks into smaller steps
- Always verify your work by READING the file contents (read_file).
- DO NOT run web servers (e.g., "php -S", "python -m http.server", "npm start"). They block execution and will cause a timeout error.
- Use "check_file_exists" to verify file creation.

PROJECT HISTORY (What you have built before):
{self._format_project_history()}

INTERNAL AGENT HISTORY (Your thoughts/actions so far in this task):
"""
        
        # Add history
        for entry in history:
            if entry["type"] == "thought":
                prompt += f"\nThought: {entry['content']}"
            elif entry["type"] == "action":
                prompt += f"\nAction: {entry['tool']}({json.dumps(entry['input'])})"
            elif entry["type"] == "observation":
                prompt += f"\nObservation: {entry['content']}"
        
        prompt += "\n\nNow, what is your next step? Respond with JSON only."
        
        return prompt
    
    def _format_project_history(self) -> str:
        """Format project history for the prompt."""
        if not self.project_history:
            return "No previous tasks recorded."
            
        summary = ""
        for entry in self.project_history[-5:]: # Show last 5 tasks
            summary += f"- {entry['timestamp'][:16]}: {entry['task']}\n"
            for action in entry['actions']:
                if action['tool'] == 'create_file':
                    summary += f"  * Created {action['input'].get('name')}\n"
                elif action['tool'] == 'create_folder':
                    summary += f"  * Created folder {action['input'].get('name')}\n"
                elif action['tool'] == 'edit_file':
                    summary += f"  * Edited {action['input'].get('name')}\n"
        return summary
    
    def execute_task(
        self, 
        task: str, 
        callback: Optional[Callable] = None, 
        conversation_history: str = "",
        user_message: str = ""
    ) -> Dict[str, Any]:
        """
        Execute a task autonomously.
        
        Args:
            task: Task description from user
            callback: Optional callback function for progress updates
            conversation_history: Recent conversation history
            user_message: Original user message
            
        Returns:
            Final result dictionary
        """
        self.current_task = task
        self.thoughts = []
        self.actions = []
        self.observations = []
        self.is_running = True
        
        logger.info(f"Starting autonomous task: {task} (Original: {user_message[:50]}...)")
        
        history = []
        iteration = 0
        
        try:
            while iteration < self.max_iterations and self.is_running:
                iteration += 1
                logger.info(f"Agent iteration {iteration}/{self.max_iterations}")
                
                # Build prompt with history
                prompt = self._build_agent_prompt(
                    task, 
                    history, 
                    conversation_history=conversation_history,
                    user_message=user_message
                )
                
                # Call LLM for next step
                try:
                    response = self._call_agent_llm(prompt)
                    
                    # Parse response
                    step = self._parse_agent_response(response)
                    
                    # Log thought
                    thought = step.get("thought", "")
                    self.thoughts.append(thought)
                    history.append({"type": "thought", "content": thought})
                    logger.info(f"Thought: {thought}")
                    
                    # Send progress update
                    if callback:
                        callback({
                            "type": "thought",
                            "content": thought,
                            "iteration": iteration
                        })
                    
                    # Check if final answer
                    if step.get("is_final", False):
                        final_answer = step.get("action_input", {}).get("answer", "Task completed")
                        logger.info(f"Task completed: {final_answer}")
                        
                        # Save to persistent history
                        self._save_history(task, self.actions)
                        
                        return {
                            "success": True,
                            "result": final_answer,
                            "iterations": iteration,
                            "thoughts": self.thoughts,
                            "actions": self.actions
                        }
                    
                    # Execute action
                    action = step.get("action", "")
                    action_input = step.get("action_input", {})
                    
                    if action not in self.tools:
                        observation = f"Error: Unknown tool '{action}'"
                        logger.error(observation)
                    else:
                        # Execute tool
                        logger.info(f"Action: {action}({json.dumps(action_input)})")
                        self.actions.append({"tool": action, "input": action_input})
                        history.append({"type": "action", "tool": action, "input": action_input})
                        
                        # Send progress update
                        if callback:
                            callback({
                                "type": "action",
                                "tool": action,
                                "input": action_input,
                                "iteration": iteration
                            })
                        
                        # Call tool
                        tool_result = self.tools[action](**action_input)
                        
                        # Format observation
                        if tool_result.get("success", False):
                            observation = f"Success: {tool_result.get('message', json.dumps(tool_result))}"
                        else:
                            observation = f"Error: {tool_result.get('error', 'Unknown error')}"
                        
                        logger.info(f"Observation: {observation}")
                        self.observations.append(observation)
                        history.append({"type": "observation", "content": observation})
                        
                        # Send progress update
                        if callback:
                            callback({
                                "type": "observation",
                                "content": observation,
                                "iteration": iteration
                            })
                
                except Exception as e:
                    logger.error(f"Error in agent iteration: {e}")
                    observation = f"System error: {str(e)}"
                    self.observations.append(observation)
                    history.append({"type": "observation", "content": observation})
            
            # Max iterations reached
            logger.warning(f"Max iterations ({self.max_iterations}) reached")
            # Check if we hit max iterations
            if iteration >= self.max_iterations:
                logger.warning(f"Max iterations ({self.max_iterations}) reached")
                
                # Soft landing: If the last action was successful (e.g. create_file), consider it a success
                # even if the agent didn't say "final_answer"
                if self.actions and self.observations and "Success" in str(self.observations[-1]):
                    last_action = self.actions[-1]
                    logger.info(f"Soft landing: Max iterations reached but last action ({last_action['tool']}) was successful.")
                    
                    final_result = f"Task stopped after {self.max_iterations} steps. Last action: {last_action['tool']} was successful."
                    self._save_history(task, self.actions)
                    
                    return {
                        "success": True,
                        "result": final_result,
                        "iterations": iteration,
                        "thoughts": self.thoughts,
                        "actions": self.actions,
                        "note": "Auto-completed due to iteration limit"
                    }
                
                return {
                    "success": False,
                    "error": f"Task did not complete within {self.max_iterations} iterations",
                    "iterations": iteration,
                    "thoughts": self.thoughts,
                    "actions": self.actions
                }
                
            return {
                "success": False,
                "error": "Agent stopped unexpectedly",
                "iterations": iteration,
                "thoughts": self.thoughts,
                "actions": self.actions
            }
        
        finally:
            self.is_running = False
    
    def _call_agent_llm(self, prompt: str) -> str:
        """
        Call LLM with agent prompt, handling rate limits.
        
        Args:
            prompt: Agent prompt
            
        Returns:
            LLM response text
        """
        import time
        
        max_retries = 3
        retry_delay = 10  # Start with 10 seconds
        
        messages = [
            {"role": "system", "content": "You are ASR-7, an autonomous AI agent with personality. Maintain your sassy, confident character while executing tasks. Always respond with valid JSON for tool calls."},
            {"role": "user", "content": prompt}
        ]
        
        for attempt in range(max_retries):
            try:
                return self.cognitive_engine._call_llm(messages)
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str:
                    logger.warning(f"Rate limit hit (429). Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                
                # If not a rate limit or retries exhausted, re-raise
                logger.error(f"LLM call failed: {e}")
                raise
        
        raise Exception("Max retries exceeded for LLM call")
    
    def _parse_agent_response(self, response: str) -> Dict[str, Any]:
        """
        Parse agent response into structured format.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed step dictionary
        """
        # Try to extract JSON
        import re
        
        # Look for JSON block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx + 1]
            else:
                raise ValueError(f"Could not extract JSON from response: {response[:200]}")
        
        # Parse JSON
        try:
            step = json.loads(json_str)
            return step
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent response: {e}")
            raise ValueError(f"Invalid JSON in agent response: {json_str[:200]}")
    
    def stop(self):
        """Stop the agent execution."""
        self.is_running = False
        logger.info("Agent execution stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current agent status.
        
        Returns:
            Status dictionary
        """
        return {
            "is_running": self.is_running,
            "current_task": self.current_task,
            "iterations": len(self.thoughts),
            "last_thought": self.thoughts[-1] if self.thoughts else None,
            "last_action": self.actions[-1] if self.actions else None
        }
