"""
Example skill: Greeting Skill
==============================
A simple demonstration skill for the JARVIS plugin system.

This skill responds to greeting intents with personalized messages.
"""

from __future__ import annotations

import random
from datetime import datetime

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult


class GreetingSkill(BaseSkill):
    """Responds to greetings with time-appropriate messages.

    Example:
        User: "Hello JARVIS"
        JARVIS: "Good evening, sir. How may I assist you tonight?"
    """

    metadata = SkillMetadata(
        name="greeting",
        version="1.0.0",
        description="Responds to greetings with personalized messages",
        author="JARVIS Team",
        tags=["greeting", "social", "conversation"],
    )

    GREETINGS = {
        "morning": [
            "Good morning, sir. I trust you slept well.",
            "Morning! All systems are operational.",
            "Good morning. Ready to tackle the day?",
        ],
        "afternoon": [
            "Good afternoon. How may I assist you?",
            "Afternoon! What can I do for you?",
            "Good afternoon, sir. All systems nominal.",
        ],
        "evening": [
            "Good evening. How may I be of service?",
            "Evening! What can I help you with tonight?",
            "Good evening, sir. I'm at your disposal.",
        ],
        "night": [
            "Working late, sir? How may I help?",
            "Night shift? I'm here if you need me.",
            "Still at it? Let me know how I can assist.",
        ],
    }

    async def execute(self, context: SkillContext) -> SkillResult:
        """Generate a time-appropriate greeting.

        Args:
            context: Execution context (user_input is the greeting).

        Returns:
            SkillResult with the greeting message.
        """
        hour = datetime.now().hour

        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 21:
            period = "evening"
        else:
            period = "night"

        greeting = random.choice(self.GREETINGS[period])

        return SkillResult(
            success=True,
            output=greeting,
            metadata={"period": period, "hour": hour},
        )
