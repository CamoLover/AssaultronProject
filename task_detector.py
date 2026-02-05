    def _detect_agent_task(self, message: str) -> tuple[bool, str]:
        """
        Detect if a user message contains an actionable task for the autonomous agent.
        
        Args:
            message: User's message
            
        Returns:
            (is_task, task_description) tuple
        """
        message_lower = message.lower()
        
        # Task trigger keywords
        action_verbs = [
            'create', 'make', 'build', 'write', 'generate', 'develop',
            'code', 'program', 'design', 'implement', 'construct',
            'research', 'find', 'search', 'look up', 'investigate',
            'analyze', 'test', 'run', 'execute', 'deploy'
        ]
        
        # File/project indicators
        creation_indicators = [
            'website', 'web page', 'html', 'css', 'javascript', 'php',
            'file', 'folder', 'directory', 'script', 'program',
            'app', 'application', 'project', 'code', 'document',
            'poem', 'story', 'article', 'report', 'summary'
        ]
        
        # Check for action verbs
        has_action = any(verb in message_lower for verb in action_verbs)
        
        # Check for creation indicators
        has_creation = any(indicator in message_lower for indicator in creation_indicators)
        
        # Detect task if both conditions are met
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
