"""
Time Awareness Module for ASR-7

Provides time analysis utilities for detecting conversation patterns,
calculating time gaps, and generating contextual observations about timing.
"""

from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TimeContext:
    """Contextual information about the current time and recent interaction patterns."""
    current_time: datetime
    time_of_day: str  # "early_morning", "morning", "afternoon", "evening", "night", "late_night"
    day_of_week: str
    is_weekend: bool
    time_since_last: Optional[float]  # hours since last message
    last_message_time: Optional[datetime]
    pattern_observation: Optional[str]  # Human-readable observation about timing patterns


def get_time_of_day(dt: datetime) -> str:
    """
    Categorize the time of day based on hour.

    Returns:
        - "early_morning" (3am-6am)
        - "morning" (6am-12pm)
        - "afternoon" (12pm-5pm)
        - "evening" (5pm-9pm)
        - "night" (9pm-12am)
        - "late_night" (12am-3am)
    """
    hour = dt.hour

    if 3 <= hour < 6:
        return "early_morning"
    elif 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    elif 21 <= hour < 24:
        return "night"
    else:  # 0-3
        return "late_night"


def calculate_time_gap(current_time: datetime, previous_time: datetime) -> Tuple[float, str]:
    """
    Calculate the time gap between two messages and provide a human-readable description.

    Args:
        current_time: Current message timestamp
        previous_time: Previous message timestamp

    Returns:
        Tuple of (hours_elapsed, human_description)
    """
    delta = current_time - previous_time
    hours = delta.total_seconds() / 3600

    if hours < 0.016:  # Less than 1 minute
        description = "just seconds ago"
    elif hours < 1:  # Less than 1 hour
        minutes = int(delta.total_seconds() / 60)
        description = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif hours < 2:
        description = "about an hour ago"
    elif hours < 24:
        hours_int = int(hours)
        description = f"{hours_int} hour{'s' if hours_int != 1 else ''} ago"
    elif hours < 48:
        description = "almost a day ago"
    else:
        days = int(hours / 24)
        description = f"{days} day{'s' if days != 1 else ''} ago"

    return hours, description


def analyze_sleep_pattern(message_times: List[datetime], current_time: datetime) -> Optional[str]:
    """
    Analyze recent message times to detect potential sleep deprivation or unusual patterns.

    Args:
        message_times: List of recent message timestamps (newest first)
        current_time: Current message timestamp

    Returns:
        Observation string if pattern detected, None otherwise
    """
    if not message_times:
        return None

    current_hour = current_time.hour
    current_tod = get_time_of_day(current_time)

    # Check if current message is late night or early morning
    if current_tod in ["late_night", "early_morning"]:
        # Count recent late night messages in the past week
        one_week_ago = current_time - timedelta(days=7)
        recent_late_messages = [
            msg_time for msg_time in message_times
            if msg_time >= one_week_ago and get_time_of_day(msg_time) in ["late_night", "early_morning"]
        ]

        if len(recent_late_messages) >= 3:
            return "repeated_late_night_activity"

    # Check for messages spanning a very long time (no sleep)
    if len(message_times) >= 2:
        time_span = (current_time - message_times[1]).total_seconds() / 3600

        # If messages span over 18 hours without a long gap, likely no sleep
        if time_span > 18:
            # Check if there was any gap longer than 4 hours (potential sleep)
            had_sleep = False
            for i in range(len(message_times) - 1):
                gap = (message_times[i] - message_times[i + 1]).total_seconds() / 3600
                if gap > 4:
                    had_sleep = True
                    break

            if not had_sleep:
                return "extended_wakefulness"

    # Check for unusual time (e.g., 3am message when recent pattern was afternoon)
    if len(message_times) >= 3:
        recent_times_of_day = [get_time_of_day(t) for t in message_times[1:4]]
        if current_tod in ["late_night", "early_morning"] and all(
            tod in ["afternoon", "evening", "morning"] for tod in recent_times_of_day
        ):
            return "unusual_late_activity"

    return None


def analyze_response_time(current_time: datetime, last_time: datetime) -> Optional[str]:
    """
    Analyze the time gap between messages and categorize it.

    Args:
        current_time: Current message timestamp
        last_time: Previous message timestamp

    Returns:
        Category string: "immediate", "normal", "delayed", "long_absence", "very_long_absence"
    """
    hours, _ = calculate_time_gap(current_time, last_time)

    if hours < 0.016:  # Less than 1 minute
        return "immediate"
    elif hours < 2:
        return "normal"
    elif hours < 6:
        return "delayed"
    elif hours < 24:
        return "long_absence"
    else:
        return "very_long_absence"


def generate_time_observation(
    current_time: datetime,
    last_message_time: Optional[datetime],
    conversation_history: List[Dict],
    mood_state: Optional[Dict] = None
) -> Optional[str]:
    """
    Generate a contextual observation about timing patterns for ASR-7 to potentially comment on.

    Args:
        current_time: Current message timestamp
        last_message_time: Previous message timestamp
        conversation_history: Recent conversation history with timestamps
        mood_state: Current mood state (optional, for more nuanced observations)

    Returns:
        Observation string for ASR-7's context, or None if no notable pattern
    """
    observations = []

    current_tod = get_time_of_day(current_time)
    current_hour = current_time.hour
    day_name = current_time.strftime("%A")

    # Time of day observations
    if current_tod == "late_night":
        observations.append(f"It's {current_hour % 12 or 12}AM - quite late at night")
    elif current_tod == "early_morning":
        observations.append(f"It's {current_hour}AM - very early morning hours")

    # Day observations
    if current_time.weekday() in [5, 6]:  # Weekend
        if current_tod in ["morning", "early_morning"]:
            observations.append(f"Weekend {current_tod.replace('_', ' ')}")

    # Time gap observations
    if last_message_time:
        hours, description = calculate_time_gap(current_time, last_message_time)
        response_category = analyze_response_time(current_time, last_message_time)

        last_tod = get_time_of_day(last_message_time)

        if response_category == "very_long_absence":
            days = int(hours / 24)
            observations.append(f"Last message was {days} day{'s' if days != 1 else ''} ago at {last_message_time.strftime('%I:%M%p').lower()} ({last_tod.replace('_', ' ')})")
        elif response_category == "long_absence":
            hours_int = int(hours)
            observations.append(f"Last message was {hours_int} hours ago at {last_message_time.strftime('%I:%M%p').lower()}")
        elif hours > 0.5:  # More than 30 minutes but less than long absence
            # Check if it spans across significant time boundaries
            if last_tod != current_tod:
                observations.append(f"Last spoke {description} during {last_tod.replace('_', ' ')}, now it's {current_tod.replace('_', ' ')}")

    # Pattern analysis
    message_times = []
    for msg in conversation_history[-10:]:  # Last 10 messages
        if "timestamp" in msg:
            try:
                msg_time = datetime.fromisoformat(msg["timestamp"])
                message_times.append(msg_time)
            except:
                pass

    message_times.sort(reverse=True)  # Newest first

    if message_times:
        pattern = analyze_sleep_pattern(message_times, current_time)
        if pattern == "repeated_late_night_activity":
            observations.append("Pattern detected: Multiple late night/early morning messages this week")
        elif pattern == "extended_wakefulness":
            observations.append("Pattern detected: Messages spanning many hours without a long break")
        elif pattern == "unusual_late_activity":
            observations.append("Pattern detected: Unusual late activity compared to recent pattern")

    return " | ".join(observations) if observations else None


def get_time_context(
    conversation_history: List[Dict],
    mood_state: Optional[Dict] = None
) -> TimeContext:
    """
    Build a complete time context for the current message.

    Args:
        conversation_history: Recent conversation history with timestamps
        mood_state: Current mood state (optional)

    Returns:
        TimeContext object with all timing information
    """
    current_time = datetime.now()
    last_message_time = None

    # Find the last message timestamp
    if conversation_history:
        for msg in reversed(conversation_history):
            if "timestamp" in msg:
                try:
                    last_message_time = datetime.fromisoformat(msg["timestamp"])
                    break
                except:
                    pass

    time_since_last = None
    if last_message_time:
        time_since_last = (current_time - last_message_time).total_seconds() / 3600

    pattern_observation = generate_time_observation(
        current_time,
        last_message_time,
        conversation_history,
        mood_state
    )

    return TimeContext(
        current_time=current_time,
        time_of_day=get_time_of_day(current_time),
        day_of_week=current_time.strftime("%A"),
        is_weekend=current_time.weekday() in [5, 6],
        time_since_last=time_since_last,
        last_message_time=last_message_time,
        pattern_observation=pattern_observation
    )


def format_time_context_for_prompt(time_context: TimeContext) -> str:
    """
    Format time context into a string suitable for including in the LLM prompt.

    Args:
        time_context: TimeContext object

    Returns:
        Formatted string for prompt inclusion
    """
    lines = []
    lines.append(f"Current Time: {time_context.current_time.strftime('%Y-%m-%d %I:%M:%S %p')}")
    lines.append(f"Time of Day: {time_context.time_of_day.replace('_', ' ').title()}")
    lines.append(f"Day: {time_context.day_of_week}")

    if time_context.time_since_last is not None:
        hours, description = calculate_time_gap(
            time_context.current_time,
            time_context.last_message_time
        )
        lines.append(f"Time Since Last Message: {description}")

    if time_context.pattern_observation:
        lines.append(f"Timing Observations: {time_context.pattern_observation}")

    return "\n".join(lines)
