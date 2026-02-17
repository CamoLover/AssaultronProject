"""
Notification Manager for Assaultron AI
Sends Discord webhook notifications when the AI needs user attention
"""

import threading
import time
import requests
from datetime import datetime
from typing import Optional
import logging
import os


class NotificationManager:
    """Manages Discord webhook notifications for AI attention requests"""

    def __init__(self, app_name: str = "Assaultron AI", webhook_url: Optional[str] = None, cognitive_engine=None):
        self.app_name = app_name
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
        self.last_notification_time = None
        self.min_notification_interval = 30  # Minimum seconds between notifications
        self.inactivity_check_enabled = False
        self.inactivity_threshold_min = 300  # 5 minutes minimum
        self.inactivity_threshold_max = 1800  # 30 minutes maximum
        self.last_user_interaction = datetime.now()
        self.check_in_thread = None
        self.cognitive_engine = cognitive_engine  # Reference to AI for generating questions
        self.next_checkin_time = None
        self.waiting_for_response = False  # Track if we sent a notification and are waiting for user response
        self.last_notification_sent_time = None  # Track when last notification was sent
        self.notification_timeout = 3600  # After 1 hour, assume no response is coming and allow new notifications
        self._notification_lock = threading.Lock()  # Thread safety for notification sending
        self.logger = logging.getLogger('assaultron.notification')

    def send_notification(self, title: str, message: str, color: int = 0x3498db, force: bool = False) -> bool:
        """
        Send a Discord webhook notification

        Args:
            title: Notification title
            message: Notification message
            color: Embed color (hex int)
            force: Skip rate limiting if True

        Returns:
            True if notification was sent, False if rate-limited
        """
        # Rate limiting to avoid spam
        if not force and self.last_notification_time:
            time_since_last = (datetime.now() - self.last_notification_time).total_seconds()
            if time_since_last < self.min_notification_interval:
                return False

        try:
            # Create Discord embed
            embed = {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": self.app_name
                }
            }

            payload = {
                "username": self.app_name,
                "embeds": [embed]
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )

            if response.status_code in [200, 204]:
                self.last_notification_time = datetime.now()
                return True
            else:
                self.logger.error(f"Discord webhook failed: {response.status_code}")
                return False

        except Exception as e:
            self.logger.exception(f"Failed to send Discord notification: {e}")
            return False

    def notify_high_urgency(self, emotion: str, goal: str, urgency: float):
        """Notification for high urgency cognitive states"""
        title = "⚠️ High Priority Alert"
        message = f"**Urgency:** {urgency:.0%}\n**Emotion:** {emotion}\n**Goal:** {goal}"
        self.send_notification(title, message, color=0xff9900)  # Orange

    def notify_threat_detected(self, threat_level: str, entity_count: int):
        """Notification for threat detection"""
        emoji_map = {"low": "ℹ️", "medium": "⚠️", "high": "🚨"}
        color_map = {"low": 0x3498db, "medium": 0xff9900, "high": 0xe74c3c}

        emoji = emoji_map.get(threat_level, "⚠️")
        color = color_map.get(threat_level, 0xff9900)

        title = f"{emoji} Threat Detected"
        message = f"**Threat Level:** {threat_level.upper()}\n**Entities Detected:** {entity_count}"
        self.send_notification(title, message, color=color, force=True)

    def notify_attention_request(self, reason: str, dialogue: str = None):
        """Notification when AI explicitly requests attention"""
        title = "💬 Assaultron Wants Your Attention"
        message = reason if reason else "I need to talk to you."
        if dialogue:
            # Truncate dialogue to keep notification readable
            message = dialogue[:200] + "..." if len(dialogue) > 200 else dialogue
        self.send_notification(title, message, color=0x9b59b6, force=True)  # Purple

    def notify_scheduled_checkin(self, message: str):
        """
        Notification for scheduled check-ins during inactivity.
        Also adds the question to conversation history so AI has context when user responds.
        """
        title = "👋 Check-In"

        # Add the AI's question to conversation history BEFORE sending notification
        if self.cognitive_engine:
            try:
                # Add as an AI message in the conversation history
                self.cognitive_engine.conversation_history.append({
                    "user": "",  # Empty user field indicates AI initiated
                    "assistant": message,
                    "timestamp": datetime.now().isoformat(),
                    "notification": True  # Flag this as a notification message
                })
                self.cognitive_engine._save_history()
                self.logger.info("Added check-in question to conversation history")
            except Exception as e:
                self.logger.error(f"Failed to add question to history: {e}")

        self.send_notification(title, message, color=0x2ecc71)  # Green

    def update_user_activity(self):
        """Call this when user interacts with the system"""
        self.last_user_interaction = datetime.now()
        # Clear waiting flag when user responds
        if self.waiting_for_response:
            self.waiting_for_response = False
            self.logger.info("User responded, will resume check-ins after next inactivity period")

    def _generate_ai_question(self) -> str:
        """
        Use the AI to generate a personalized check-in question based on context.

        Returns:
            A thoughtful question from the AI
        """
        if not self.cognitive_engine:
            # Fallback if no AI available
            import random
            return random.choice([
                "Hey! Been thinking about you. How's everything going?",
                "Just checking in - anything interesting happen today?",
                "Still here watching over things. Want to chat about something?",
            ])

        try:
            # Get conversation context
            from virtual_body import WorldState, BodyState

            # Build a prompt for the AI to generate a thoughtful question
            memory_summary = self.cognitive_engine.get_memory_summary()
            recent_context = ""
            if self.cognitive_engine.conversation_history:
                last_exchange = self.cognitive_engine.conversation_history[-1]
                recent_context = f"Last thing we talked about: {last_exchange.get('user', 'N/A')}"

            prompt = f"""You haven't heard from your operator Evan in a while. Based on what you know about him and your recent conversations, generate ONE thoughtful question to check in on him.

{memory_summary}

{recent_context}

The question should be:
- Personal and show you've been thinking about him
- Related to previous conversations or things you know about him
- Curious, friendly, and conversational
- Short (one sentence)

Just return the question, nothing else. Don't use asterisks or formatting."""

            # Create a simple message list for the AI
            messages = [
                {"role": "system", "content": "You are ASR-7 Assaultron, checking in on your operator Evan after a period of silence. Generate a thoughtful, personal question."},
                {"role": "user", "content": prompt}
            ]

            # Call the LLM
            response = self.cognitive_engine._call_llm(messages)

            # Clean up the response - handle JSON arrays and quotes
            question = response.strip()

            # Remove JSON array brackets if present
            if question.startswith('[') and question.endswith(']'):
                # Extract content from array, remove quotes
                import json
                try:
                    parsed = json.loads(question)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        question = str(parsed[0])
                except:
                    # If JSON parsing fails, just strip the brackets
                    question = question.strip('[]').strip()

            # Remove any remaining quotes
            question = question.strip('"').strip("'").strip()

            # Validate it's actually a question
            if not question.endswith('?'):
                question += '?'

            return question

        except Exception as e:
            self.logger.error(f"Failed to generate AI question: {e}")
            import random
            return random.choice([
                "Hey! Been thinking about you. How's everything going?",
                "Just checking in - anything interesting happen today?",
            ])

    def start_inactivity_monitoring(self, check_interval: int = 60):
        """
        Start background thread to monitor for inactivity with randomized check-in times.
        AI generates personalized questions based on conversation history.

        Args:
            check_interval: How often to check for inactivity (seconds)
        """
        if self.check_in_thread and self.check_in_thread.is_alive():
            self.logger.warning("Monitoring thread already running, skipping start")
            return  # Already running

        self.inactivity_check_enabled = True
        self.waiting_for_response = False  # Reset waiting flag when starting fresh

        # Set initial random check-in time
        import random
        initial_wait = random.randint(self.inactivity_threshold_min, self.inactivity_threshold_max)
        self.next_checkin_time = datetime.now()

        def inactivity_loop():
            import random

            while self.inactivity_check_enabled:
                time.sleep(check_interval)

                if not self.inactivity_check_enabled:
                    break

                time_since_interaction = (datetime.now() - self.last_user_interaction).total_seconds()

                # Pick random check-in interval (5-30 minutes)
                check_in_threshold = random.randint(self.inactivity_threshold_min, self.inactivity_threshold_max)

                if time_since_interaction >= check_in_threshold:
                    # Double-check enabled flag before doing any work
                    if not self.inactivity_check_enabled:
                        break

                    # Use lock to ensure only one notification is sent at a time
                    with self._notification_lock:
                        # Check if we're still waiting for a response
                        if self.waiting_for_response:
                            # Check if the notification has timed out (user probably isn't responding)
                            if self.last_notification_sent_time:
                                time_since_notification = (datetime.now() - self.last_notification_sent_time).total_seconds()
                                if time_since_notification > self.notification_timeout:
                                    self.logger.info(f"Previous notification timed out after {time_since_notification/60:.1f} minutes, allowing new notification")
                                    self.waiting_for_response = False
                                else:
                                    self.logger.debug(f"Already waiting for user response ({time_since_notification/60:.1f} min ago), skipping check-in")
                                    continue
                            else:
                                # Flag is set but no timestamp - this is an error state, reset it
                                self.logger.warning("waiting_for_response=True but no timestamp found. Resetting flag (likely from old session)")
                                self.waiting_for_response = False

                        self.logger.info(f"{time_since_interaction:.0f}s of inactivity detected")
                        self.logger.debug(f"waiting_for_response={self.waiting_for_response}, proceeding with notification")
                        self.logger.info("Generating AI question...")

                        # Generate AI question
                        question = self._generate_ai_question()
                        self.logger.info(f"AI question: {question}")

                        # Check flag again before sending notification
                        if not self.inactivity_check_enabled:
                            break

                        # Send it and mark that we're waiting for response
                        self.logger.info("Sending notification and setting waiting_for_response=True")
                        self.notify_scheduled_checkin(question)
                        self.waiting_for_response = True
                        self.last_notification_sent_time = datetime.now()
                        self.logger.info(f"Notification sent at {self.last_notification_sent_time.strftime('%H:%M:%S')}, waiting_for_response is now: {self.waiting_for_response}")

                        # DO NOT reset last_user_interaction here!
                        # It should only be updated when user actually interacts (via update_user_activity)
                        # This was causing notifications to be sent even while user was actively chatting
                        next_wait = random.randint(self.inactivity_threshold_min, self.inactivity_threshold_max)
                        self.logger.debug(f"Next check will be in {next_wait/60:.1f} minutes (but will skip if still waiting for response)")

        self.check_in_thread = threading.Thread(target=inactivity_loop, daemon=True)
        self.check_in_thread.start()
        self.logger.info(f"Inactivity monitoring started (check-ins every {self.inactivity_threshold_min/60:.0f}-{self.inactivity_threshold_max/60:.0f} min)")

    def stop_inactivity_monitoring(self):
        """Stop the inactivity monitoring thread"""
        self.inactivity_check_enabled = False
        self.waiting_for_response = False  # Clear waiting flag when stopping

    def configure(self, min_interval: int = None, inactivity_threshold_min: int = None, inactivity_threshold_max: int = None, webhook_url: str = None):
        """
        Configure notification settings

        Args:
            min_interval: Minimum seconds between notifications
            inactivity_threshold_min: Minimum seconds before check-in (default 300 = 5 min)
            inactivity_threshold_max: Maximum seconds before check-in (default 1800 = 30 min)
            webhook_url: Discord webhook URL
        """
        if min_interval is not None:
            self.min_notification_interval = min_interval
        if inactivity_threshold_min is not None:
            self.inactivity_threshold_min = inactivity_threshold_min
        if inactivity_threshold_max is not None:
            self.inactivity_threshold_max = inactivity_threshold_max
        if webhook_url is not None:
            self.webhook_url = webhook_url
