"""
JARVIS Brain module.
====================
AI reasoning engine with memory, context, tools, planning, personality,
emotion detection, streaming, and session management.

Quick Start:
    from jarvis.core.brain import ReasoningEngine
    engine = ReasoningEngine(settings)
    await engine.initialize()
    response = await engine.process("What's the weather in London?")
"""

from jarvis.core.brain.engine import ReasoningEngine, ReasoningResponse, ReasoningMetrics
from jarvis.core.brain.memory import ConversationMemory, Message, MessageRole, Fact
from jarvis.core.brain.context import ContextEngine, ContextSnapshot
from jarvis.core.brain.tools import ToolRegistry, ToolResult, ToolParameter, ToolCategory
from jarvis.core.brain.prompts import PromptEngine, PromptSection
from jarvis.core.brain.personality import PersonalityManager, PersonalityProfile
from jarvis.core.brain.emotion import EmotionDetector, Emotion, EmotionResult
from jarvis.core.brain.planner import TaskPlanner, TaskPlan, PlanStep, StepType
from jarvis.core.brain.streaming import StreamingGenerator, StreamChunk, StreamMetrics
from jarvis.core.brain.summarizer import ConversationSummarizer, ConversationSummary
from jarvis.core.brain.session import SessionManager, Session, SessionStatus
# Legacy compat
from jarvis.core.brain.module import BrainModule, BrainResponse, Intent

__all__ = [
    # Engine
    "ReasoningEngine",
    "ReasoningResponse",
    "ReasoningMetrics",
    # Memory
    "ConversationMemory",
    "Message",
    "MessageRole",
    "Fact",
    # Context
    "ContextEngine",
    "ContextSnapshot",
    # Tools
    "ToolRegistry",
    "ToolResult",
    "ToolParameter",
    "ToolCategory",
    # Prompts
    "PromptEngine",
    "PromptSection",
    # Personality
    "PersonalityManager",
    "PersonalityProfile",
    # Emotion
    "EmotionDetector",
    "Emotion",
    "EmotionResult",
    # Planning
    "TaskPlanner",
    "TaskPlan",
    "PlanStep",
    "StepType",
    # Streaming
    "StreamingGenerator",
    "StreamChunk",
    "StreamMetrics",
    # Summarizer
    "ConversationSummarizer",
    "ConversationSummary",
    # Sessions
    "SessionManager",
    "Session",
    "SessionStatus",
    # Legacy
    "BrainModule",
    "BrainResponse",
    "Intent",
]
