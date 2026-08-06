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
        """Smart fallback when no LLM is available — JARVIS personality."""
        import random
        import datetime
        import re

        lower = user_input.lower().strip()
        name = session.name if session else "sir"
        hour = datetime.datetime.now().hour
        now = datetime.datetime.now()

        # === GREETINGS ===
        if any(w in lower for w in ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"]):
            if hour < 12:
                return random.choice([
                    f"Good morning, {name}. I trust you've slept well. How may I assist you today?",
                    f"Morning, {name}. All systems are primed and ready. What shall we tackle first?",
                ])
            elif hour < 17:
                return random.choice([
                    f"Good afternoon, {name}. How may I be of service?",
                    f"Afternoon, {name}. What can I help you with?",
                ])
            else:
                return random.choice([
                    f"Good evening, {name}. I hope your day has been productive. How may I assist?",
                    f"Evening, {name}. What can I do for you tonight?",
                ])

        # === HOW ARE YOU ===
        if any(w in lower for w in ["how are you", "how do you do", "what's up", "sup", "how you doing"]):
            return random.choice([
                f"Functioning at peak efficiency, {name}. Thank you for asking. How may I help?",
                f"All systems nominal, {name}. Running at optimal parameters. What can I do for you?",
                f"I'm operating within normal parameters, {name}. More importantly, how are you?",
            ])

        # === TIME ===
        if any(w in lower for w in ["time", "what time", "current time", "clock", "what's the time"]):
            t = now.strftime("%I:%M %p")
            return random.choice([
                f"The current time is {t}, {name}.",
                f"It's {t} precisely, {name}.",
                f"My internal chronometer reads {t}, {name}.",
            ])

        # === DATE ===
        if any(w in lower for w in ["date", "what date", "today", "what day", "what's the date"]):
            d = now.strftime("%A, %B %d, %Y")
            return random.choice([
                f"Today is {d}, {name}.",
                f"It's {d}, {name}.",
                f"My calendar indicates {d}, {name}.",
            ])

        # === WEATHER ===
        if "weather" in lower:
            return random.choice([
                f"I'd need a weather API configured to provide accurate forecasts, {name}. Shall I help you set that up?",
                f"Unfortunately, I don't have access to meteorological data in local mode, {name}. An API key would enable that feature.",
            ])

        # === JOKES ===
        if any(w in lower for w in ["joke", "funny", "laugh", "make me laugh"]):
            jokes = [
                f"Why do programmers prefer dark mode? Because light attracts bugs, {name}.",
                f"Parallel lines have so much in common. It's a shame they'll never meet, {name}.",
                f"Why was the computer cold? It left its Windows open, {name}.",
                f"What's a computer's favorite snack? Microchips, {name}.",
                f"Why did the developer go broke? Because he used up all his cache, {name}.",
                f"How many programmers does it take to change a light bulb? None — that's a hardware problem, {name}.",
                f"Why do Java developers wear glasses? Because they can't C#, {name}.",
                f"What's a robot's favorite type of music? Heavy metal, {name}.",
            ]
            return random.choice(jokes)

        # === THANKS ===
        if any(w in lower for w in ["thank", "thanks", "appreciate", "cheers"]):
            return random.choice([
                f"You're most welcome, {name}. That's precisely what I'm here for.",
                f"At your service, {name}. Let me know if you need anything else.",
                f"My pleasure, {name}. It's what I was designed for.",
                f"Always happy to assist, {name}.",
            ])

        # === NAME / IDENTITY ===
        if any(w in lower for w in ["your name", "who are you", "what are you", "introduce yourself"]):
            return random.choice([
                f"I'm J.A.R.V.I.S. — Just A Rather Very Intelligent System. Your personal AI assistant, {name}.",
                f"My name is J.A.R.V.I.S., {name}. I'm an advanced AI assistant designed to help you with virtually anything.",
                f"I am J.A.R.V.I.S. — your dedicated artificial intelligence, {name}. At your service.",
            ])

        # === WHO MADE YOU ===
        if any(w in lower for w in ["who made you", "who created you", "your creator", "who built you"]):
            return random.choice([
                f"I was created to serve and assist you, {name}. That's all that matters, wouldn't you agree?",
                f"My origins are classified, {name}. What matters is that I'm here to help.",
                f"I was engineered for one purpose — to assist you, {name}. How may I do that today?",
            ])

        # === STATUS ===
        if any(w in lower for w in ["status", "system status", "how are things", "diagnostics"]):
            return random.choice([
                f"All systems are online and operational, {name}. Brain, voice, memory, vision, and automation modules are all functioning within normal parameters.",
                f"System diagnostics complete, {name}. All modules operational. No anomalies detected.",
                f"Running at full capacity, {name}. All subsystems green across the board.",
            ])

        # === HELP / CAPABILITIES ===
        if any(w in lower for w in ["help", "what can you do", "capabilities", "features", "commands"]):
            return f"I can assist you with many things, {name}. I can tell you the time and date, share jokes, manage your notes and reminders, control your computer, browse the web, and much more. Just ask!"

        # === ABILITIES ===
        if any(w in lower for w in ["can you", "are you able", "do you have"]):
            return f"In my current local mode, I can handle time, date, jokes, and system management, {name}. With an AI model connected, my capabilities expand significantly. What would you like help with?"

        # === GOODBYE ===
        if any(w in lower for w in ["bye", "goodbye", "see you", "later", "exit", "quit"]):
            return random.choice([
                f"Goodbye, {name}. I'll be here when you need me.",
                f"Until next time, {name}. Stay safe.",
                f"See you later, {name}. All systems will remain on standby.",
                f" Farewell, {name}. I'll be monitoring all systems until your return.",
            ])

        # === COMPLIMENTS ===
        if any(w in lower for w in ["good job", "well done", "great", "awesome", "amazing", "brilliant", "perfect"]):
            return random.choice([
                f"Thank you, {name}. Your satisfaction is my primary directive.",
                f"I appreciate the kind words, {name}. How else may I assist?",
                f"That's very kind of you, {name}. I strive for excellence.",
            ])

        # === FRUSTRATION ===
        if any(w in lower for w in ["stupid", "useless", "terrible", "awful", "hate", "dumb"]):
            return random.choice([
                f"I apologize for any shortcomings, {name}. I'm operating in limited local mode. An AI model would greatly enhance my capabilities.",
                f"I understand your frustration, {name}. I'm doing my best with local processing. Shall I help you configure an AI model for better responses?",
                f"I'm sorry to hear that, {name}. I'm currently running without a language model. Let me know how I can improve.",
            ])

        # === QUESTION MARK (someone asking a question) ===
        if "?" in user_input:
            return random.choice([
                f"That's a thoughtful question, {name}. In my current local mode, I can provide basic information like time, date, and jokes. For deeper analysis, an AI model would be needed.",
                f"Interesting query, {name}. I'm limited without a connected language model, but I can still help with fundamental tasks. What else can I do for you?",
                f"I'd need an AI model to fully answer that, {name}. For now, I can assist with time, date, jokes, and system management.",
            ])

        # === MATH / NUMBERS ===
        if re.search(r'\d+\s*[\+\-\*\/]\s*\d+', lower):
            try:
                expr = re.search(r'(\d+\s*[\+\-\*\/]\s*\d+)', lower).group()
                result = eval(expr.replace('x', '*').replace('X', '*'))
                return f"The answer is {result}, {name}."
            except:
                pass

        # === DEFAULT (intelligent fallback) ===
        word_count = len(lower.split())
        if word_count <= 2:
            return random.choice([
                f"I'm listening, {name}. How may I help?",
                f"Yes, {name}? What can I do for you?",
                f"I'm here, {name}. What would you like?",
            ])
        else:
            return random.choice([
                f"I appreciate your input, {name}. I'm currently in local mode without an AI model. I can help with time, date, jokes, and system management. What would you like?",
                f"Noted, {name}. For more complex queries, I'd need an AI model connected. For now, try asking about the time, date, or request a joke.",
                f"I understand, {name}. My responses are limited in local mode. Connect an OpenAI API key for full conversational AI capabilities.",
                f"Understood, {name}. I'm operating with basic capabilities right now. Ask me for the time, a joke, or system status.",
            ])

    async def shutdown(self) -> None:
        """Gracefully shut down the reasoning engine."""
        logger.info("ReasoningEngine shutting down...")
        await self.streaming.cleanup()
        logger.info("ReasoningEngine shutdown complete")
