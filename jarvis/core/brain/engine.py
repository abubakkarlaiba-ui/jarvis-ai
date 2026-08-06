"""
Reasoning engine — the central AI orchestrator for JARVIS.
=========================================================
Integrates all brain subsystems into a unified reasoning pipeline:

    User Input
        │
        ▼
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │   Session    │────▶│   Emotion    │────▶│   Context    │
    │   Manager    │     │   Detector   │     │   Engine     │
    └──────────────┘     └──────────────┘     └──────────────┘
                                                        │
        ┌───────────────────────────────────────────────┘
        ▼
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │   Memory     │────▶│   Prompt     │────▶│  Streaming   │
    │   System     │     │   Engine     │     │  Generator   │
    └──────────────┘     └──────────────┘     └──────────────┘
                                                        │
        ┌───────────────────────────────────────────────┘
        ▼
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │    Tool      │◀───▶│   Planner    │◀───▶│   Reasoning  │
    │   Registry   │     │              │     │    Chain     │
    └──────────────┘     └──────────────┘     └──────────────┘
                                                        │
        ┌───────────────────────────────────────────────┘
        ▼
    Response + Memory Update + Summary

This module is the single entry point for all AI reasoning.

Usage:
    engine = ReasoningEngine(settings)
    await engine.initialize()
    response = await engine.process("What's the weather in London?")
    async for token in engine.stream("Tell me about quantum computing"):
        print(token, end="")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

from jarvis.config.settings import AISettings
from jarvis.core.brain.memory import ConversationMemory, Message, MessageRole
from jarvis.core.brain.context import ContextEngine, ContextSnapshot
from jarvis.core.brain.tools import ToolRegistry, ToolResult
from jarvis.core.brain.prompts import PromptEngine
from jarvis.core.brain.personality import PersonalityManager
from jarvis.core.brain.emotion import EmotionDetector, EmotionResult, Emotion
from jarvis.core.brain.planner import TaskPlanner, TaskPlan, PlanStatus, StepStatus, StepType
from jarvis.core.brain.streaming import StreamingGenerator, StreamMetrics
from jarvis.core.brain.summarizer import ConversationSummarizer
from jarvis.core.brain.session import SessionManager, Session

logger = logging.getLogger(__name__)


@dataclass
class ReasoningMetrics:
    """Performance metrics for the reasoning engine."""
    total_requests: int = 0
    average_latency_ms: float = 0.0
    average_first_token_ms: float = 0.0
    total_tool_calls: int = 0
    total_tokens_generated: int = 0
    plans_created: int = 0
    plans_completed: int = 0
    errors: int = 0
    _total_latency_ms: float = 0.0

    def record_request(self, latency_ms: float, first_token_ms: float = 0.0) -> None:
        self.total_requests += 1
        self._total_latency_ms += latency_ms
        self.average_latency_ms = self._total_latency_ms / self.total_requests
        if first_token_ms > 0:
            self.average_first_token_ms = (
                (self.average_first_token_ms * (self.total_requests - 1) + first_token_ms)
                / self.total_requests
            )


@dataclass
class ReasoningResponse:
    """Complete response from the reasoning engine."""
    text: str
    session_id: str
    emotion: EmotionResult | None = None
    tools_used: list[str] = field(default_factory=list)
    plan: TaskPlan | None = None
    metrics: StreamMetrics | None = None
    context: ContextSnapshot | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def requires_action(self) -> bool:
        return bool(self.tools_used)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "session_id": self.session_id,
            "tools_used": self.tools_used,
            "emotion": self.emotion.emotion.value if self.emotion else None,
            "metadata": self.metadata,
        }


class ReasoningEngine:
    """The central AI reasoning engine for JARVIS.

    Orchestrates all brain subsystems to process user inputs and
    generate intelligent, context-aware, personality-driven responses.

    Pipeline:
        1. Session management (load/create session)
        2. Emotion detection (analyze user state)
        3. Context building (assemble situation awareness)
        4. Memory retrieval (load conversation + facts)
        5. Planning (decompose complex requests)
        6. Prompt construction (build system prompt)
        7. LLM generation (stream or batch)
        8. Tool execution (if function calls returned)
        9. Response modulation (personality + emotion)
        10. Memory update (store conversation turn)

    Example:
        engine = ReasoningEngine(settings)
        await engine.initialize()
        response = await engine.process("What's the weather in London?")
        print(response.text)
    """

    def __init__(self, settings: AISettings):
        self._settings = settings

        # Subsystems
        self.memory = ConversationMemory(settings)
        self.context_engine = ContextEngine(settings)
        self.tools = ToolRegistry(settings)
        self.prompt_engine = PromptEngine(settings)
        self.personality = PersonalityManager(settings)
        self.emotion_detector = EmotionDetector(settings)
        self.planner = TaskPlanner(settings)
        self.streaming = StreamingGenerator(settings)
        self.summarizer = ConversationSummarizer(settings)
        self.sessions = SessionManager(settings)

        self._metrics = ReasoningMetrics()
        self._initialized = False

        # Custom response handlers (for tool result integration)
        self._tool_result_handler: Callable | None = None

    async def initialize(self) -> None:
        """Initialize all reasoning subsystems."""
        if self._initialized:
            return

        await self.memory.initialize()
        await self.streaming.initialize()

        # Wire built-in tools to the memory system
        self._wire_builtin_tools()

        self._initialized = True
        logger.info("ReasoningEngine initialized — all subsystems online")

    def _wire_builtin_tools(self) -> None:
        """Connect built-in tools to their actual implementations."""
        remember_tool = self.tools.get_tool("remember")
        if remember_tool:
            async def remember_handler(content: str, category: str = "general") -> str:
                await self.memory.store_fact(content, category)
                return f"I'll remember that: {content}"
            remember_tool.handler = remember_handler

        recall_tool = self.tools.get_tool("recall")
        if recall_tool:
            async def recall_handler(query: str) -> str:
                facts = await self.memory.search_long_term(query, limit=5)
                if facts:
                    return "I found these relevant memories:\n" + "\n".join(
                        f"- {f.content}" for f in facts
                    )
                return "I don't have any stored memories matching that query."
            recall_tool.handler = recall_handler

    async def process(
        self,
        user_input: str,
        session_id: str | None = None,
        context: dict | None = None,
        stream: bool = False,
    ) -> ReasoningResponse:
        """Process a user input through the full reasoning pipeline.

        This is the primary entry point for synchronous processing.

        Args:
            user_input: The user's message.
            session_id: Session to use (creates new if None).
            context: Additional context from the caller.
            stream: Whether to use streaming generation.

        Returns:
            ReasoningResponse with the generated reply and metadata.
        """
        start = time.perf_counter()

        try:
            # 1. Session management
            session = await self._resolve_session(session_id)

            # 2. Store user message
            await self.memory.add_message(session.id, "user", user_input)

            # 3. Emotion detection
            emotion = self.emotion_detector.detect(user_input, session.id)
            self.context_engine.update_user_emotion(session.id, emotion.emotion.value)

            # 4. Build context snapshot
            context_snapshot = await self.context_engine.build_snapshot(
                session.id, self.memory, user_input,
            )

            # 5. Check if planning is needed
            plan = None
            complexity = self.planner.estimate_complexity(user_input)
            if complexity in ("moderate", "complex") and self._settings.tool_calling_enabled:
                plan = await self._create_and_execute_plan(
                    user_input, session, context_snapshot
                )

            # 6. Build messages for LLM
            messages = await self._build_messages(
                session.id, user_input, context_snapshot
            )

            # 7. Get tool schemas
            tool_schemas = self.tools.get_schemas() if self._settings.tool_calling_enabled else None

            # 8. Generate response
            if stream:
                text, tool_calls, stream_metrics = await self._generate_streaming(
                    messages, tool_schemas
                )
            else:
                text, tool_calls, stream_metrics = await self._generate_batch(
                    messages, tool_schemas
                )

            # 8b. Fallback if LLM returned error
            if text.startswith("[LLM not available]") or not text.strip():
                text = self._fallback_response(user_input, session)

            # 9. Execute any tool calls
            tools_used = []
            if tool_calls:
                text, tools_used = await self._execute_tool_calls(
                    tool_calls, session.id, messages
                )

            # 10. Modulate response
            text = self.personality.modulate_response(text, context_snapshot)
            text = self.emotion_detector.modulate_response(text, emotion)

            # 11. Store assistant response
            await self.memory.add_message(session.id, "assistant", text)

            # 12. Update context
            session.touch()
            session.message_count += 2

            # 13. Check for summarization
            st = self.memory._get_short_term(session.id)
            if self.summarizer.should_summarize(st.size):
                await self._summarize_if_needed(session)

            # Record metrics
            latency = (time.perf_counter() - start) * 1000
            self._metrics.record_request(latency, stream_metrics.first_token_ms if stream_metrics else 0)
            if tools_used:
                self._metrics.total_tool_calls += len(tools_used)

            return ReasoningResponse(
                text=text,
                session_id=session.id,
                emotion=emotion,
                tools_used=tools_used,
                plan=plan,
                metrics=stream_metrics,
                context=context_snapshot,
                metadata={
                    "complexity": complexity,
                    "prompt_tokens": stream_metrics.tokens_generated if stream_metrics else 0,
                },
            )

        except Exception as exc:
            self._metrics.errors += 1
            latency = (time.perf_counter() - start) * 1000
            logger.error("Reasoning failed after %.1fms: %s", latency, exc, exc_info=True)
            return ReasoningResponse(
                text=f"I encountered an error processing your request: {exc}",
                session_id=session_id or "error",
                metadata={"error": str(exc)},
            )

    async def stream(
        self,
        user_input: str,
        session_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response token by token.

        Args:
            user_input: The user's message.
            session_id: Session to use.

        Yields:
            Response text tokens as they are generated.
        """
        session = self._resolve_session(session_id)
        await self.memory.add_message(session.id, "user", user_input)

        emotion = self.emotion_detector.detect(user_input, session.id)
        self.context_engine.update_user_emotion(session.id, emotion.emotion.value)

        context_snapshot = await self.context_engine.build_snapshot(
            session.id, self.memory, user_input,
        )

        messages = await self._build_messages(session.id, user_input, context_snapshot)
        tool_schemas = self.tools.get_schemas() if self._settings.tool_calling_enabled else None

        full_text = ""
        async for chunk in self.streaming.stream(messages, tool_schemas):
            if chunk.delta:
                full_text += chunk.delta
                yield chunk.delta

            # Handle tool calls in streaming
            if chunk.tool_calls and chunk.finish_reason == "stop":
                result_text, _ = await self._execute_tool_calls(
                    chunk.tool_calls, session.id, messages
                )
                if result_text != full_text:
                    yield result_text[len(full_text):]
                    full_text = result_text

        # Store the complete response
        if full_text:
            await self.memory.add_message(session.id, "assistant", full_text)

    async def _resolve_session(self, session_id: str | None) -> Session:
        """Get or create a session."""
        if session_id:
            return self.sessions.get_or_create(session_id)
        active = self.sessions.get_active()
        if active:
            return active
        return self.sessions.create_session()

    async def _build_messages(
        self,
        session_id: str,
        user_input: str,
        context: ContextSnapshot,
    ) -> list[dict[str, Any]]:
        """Build the message list for LLM consumption."""
        # Get personality profile
        profile = self.personality.get_profile()

        # Build system prompt
        tool_names = [t["function"]["name"] for t in self.tools.get_schemas()]
        system_prompt = await self.prompt_engine.build_system_prompt(
            context=context,
            personality="formal" if profile.formality_level > 0.7 else "concise",
            available_tools=tool_names if tool_names else None,
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        history = await self.memory.get_context(session_id, max_tokens=6000)
        for msg in history:
            if msg.role != MessageRole.SYSTEM:
                messages.append({"role": msg.role.value, "content": msg.content})

        # Add current user message
        messages.append({"role": "user", "content": user_input})

        return messages

    async def _generate_batch(
        self,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> tuple[str, list[dict], StreamMetrics]:
        """Generate a complete (non-streaming) response."""
        return await self.streaming.generate(messages, tools)

    async def _generate_streaming(
        self,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> tuple[str, list[dict], StreamMetrics]:
        """Generate a streaming response and collect the result."""
        return await self.streaming.generate(messages, tools)

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict],
        session_id: str,
        messages: list[dict],
    ) -> tuple[str, list[str]]:
        """Execute tool calls and integrate results.

        Returns:
            Tuple of (final_response_text, list_of_tool_names_used).
        """
        tools_used = []
        results_text_parts = []

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args_str = func.get("arguments", "{}")

            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}

            tools_used.append(name)
            result = await self.tools.execute(name, args)

            if result.success:
                results_text_parts.append(f"[{name}] {result.output}")
            else:
                results_text_parts.append(f"[{name} error] {result.error}")

        # After tool execution, generate a synthesis response
        if results_text_parts:
            tool_context = "\n".join(results_text_parts)
            messages_with_tools = messages + [
                {"role": "system", "content": f"Tool execution results:\n{tool_context}\n\nSynthesize these results into a helpful response."},
            ]
            synthesis, _, _ = await self.streaming.generate(messages_with_tools)
            return synthesis, tools_used

        return "", tools_used

    async def _create_and_execute_plan(
        self,
        user_input: str,
        session: Session,
        context: ContextSnapshot,
    ) -> TaskPlan:
        """Create and partially execute a task plan."""
        tool_names = [t["function"]["name"] for t in self.tools.get_schemas()]
        plan = await self.planner.create_plan(user_input, context, tool_names)
        self._metrics.plans_created += 1

        logger.info("Plan created with %d steps", len(plan.steps))
        return plan

    async def _summarize_if_needed(self, session: Session) -> None:
        """Summarize old messages if the conversation is too long."""
        st = self.memory._get_short_term(session.id)
        messages = [{"role": m.role.value, "content": m.content} for m in st.get_recent()]
        summary = await self.summarizer.summarize(messages)

        if summary.text:
            # Store summary as a fact
            await self.memory.store_fact(
                summary.text,
                category="conversation_summary",
                source_session=session.id,
            )
            logger.info("Conversation summarized: %s", summary.text[:100])

    # ── Public control methods ───────────────────────────────────────

    def get_status(self) -> dict:
        """Return comprehensive engine status."""
        return {
            "initialized": self._initialized,
            "metrics": {
                "total_requests": self._metrics.total_requests,
                "avg_latency_ms": round(self._metrics.average_latency_ms, 1),
                "avg_first_token_ms": round(self._metrics.average_first_token_ms, 1),
                "total_tool_calls": self._metrics.total_tool_calls,
                "errors": self._metrics.errors,
            },
            "sessions": self.sessions.get_stats(),
            "memory": self.memory.get_stats(),
            "personality": self.personality.active_name,
            "tools": len(self.tools.list_tools()),
        }

    def _fallback_response(self, user_input: str, session) -> str:
        """Smart fallback when no LLM is available."""
        import random
        import datetime

        lower = user_input.lower().strip()
        name = session.name if session else "sir"
        hour = datetime.datetime.now().hour

        # Time-based greetings
        if any(w in lower for w in ["hello", "hi", "hey", "greetings"]):
            if hour < 12:
                return f"Good morning, {name}. How may I assist you today?"
            elif hour < 17:
                return f"Good afternoon, {name}. What can I do for you?"
            else:
                return f"Good evening, {name}. How may I be of service?"

        # How are you
        if any(w in lower for w in ["how are you", "how do you do", "what's up", "sup"]):
            return f"All systems are functioning within normal parameters, {name}. Thank you for asking. How can I help you?"

        # Time
        if any(w in lower for w in ["time", "what time", "current time", "clock"]):
            now = datetime.datetime.now().strftime("%I:%M %p")
            return f"The current time is {now}, {name}."

        # Date
        if any(w in lower for w in ["date", "what date", "today", "what day"]):
            now = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return f"Today is {now}, {name}."

        # Weather
        if "weather" in lower:
            return f"I'd love to check the weather for you, {name}, but I need an API key configured for weather data. Would you like me to help you set that up?"

        # Jokes
        if any(w in lower for w in ["joke", "funny", "laugh"]):
            jokes = [
                f"Why do programmers prefer dark mode? Because light attracts bugs, {name}.",
                f"Parallel lines have so much in common. It's a shame they'll never meet, {name}.",
                f"Why was the computer cold? It left its Windows open, {name}.",
                f"What's a computer's favorite snack? Microchips, {name}.",
                f"Why did the developer go broke? Because he used up all his cache, {name}.",
            ]
            return random.choice(jokes)

        # Thanks
        if any(w in lower for w in ["thank", "thanks", "appreciate"]):
            return random.choice([
                f"You're welcome, {name}. That's what I'm here for.",
                f"Always happy to help, {name}.",
                f"My pleasure, {name}. Let me know if you need anything else.",
            ])

        # Name
        if any(w in lower for w in ["your name", "who are you", "what are you"]):
            return f"I'm J.A.R.V.I.S. — Just A Rather Very Intelligent System. Your personal AI assistant, {name}."

        # Who made you
        if any(w in lower for w in ["who made you", "who created you", "your creator"]):
            return f"I was created to serve and assist you, {name}. That's all that matters, wouldn't you agree?"

        # Status
        if any(w in lower for w in ["status", "system status", "how are things"]):
            return f"All systems are online and operational, {name}. Brain, voice, memory, vision, and automation modules are all functioning normally."

        # Help
        if any(w in lower for w in ["help", "what can you do", "capabilities"]):
            return f"I can assist you with many things, {name}. I can tell you the time and date, share jokes, manage your notes and reminders, control your computer, browse the web, and much more. Just ask!"

        # Goodbye
        if any(w in lower for w in ["bye", "goodbye", "see you", "later"]):
            return random.choice([
                f"Goodbye, {name}. I'll be here when you need me.",
                f"Until next time, {name}. Stay safe.",
                f"See you later, {name}. All systems will remain on standby.",
            ])

        # Default
        return random.choice([
            f"I understand, {name}. I'm currently running in local mode without an AI model connected. To get smarter responses, configure an OpenAI API key in the settings.",
            f"That's an interesting point, {name}. I'm operating in local mode right now. For full AI capabilities, an API key would need to be configured.",
            f"Noted, {name}. I'm here and ready to help. For more advanced responses, I'll need an AI model connection set up.",
            f"I'm listening, {name}. Currently I'm running locally without a language model. I can still help with basic tasks like time, date, jokes, and system management.",
        ])

    async def shutdown(self) -> None:
        """Gracefully shut down the reasoning engine."""
        logger.info("ReasoningEngine shutting down...")
        await self.streaming.cleanup()
        logger.info("ReasoningEngine shutdown complete")
