"""
Streaming response generator for JARVIS.
=========================================
Provides real-time token-by-token streaming of LLM responses.

Supports multiple backends:
    - OpenAI API streaming
    - Local model streaming (via SSE or websocket)
    - Fallback to batch generation

The streaming interface allows the UI to display responses as they're
generated, providing a more natural conversation experience.

Usage:
    generator = StreamingGenerator(settings)
    async for token in generator.stream(messages, tools):
        display(token)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

from jarvis.config.settings import AISettings

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""
    text: str
    delta: str  # incremental text
    finish_reason: str | None = None
    tool_calls: list[dict] | None = None
    usage: dict | None = None
    index: int = 0


@dataclass
class StreamMetrics:
    """Metrics for a streaming response."""
    first_token_ms: float = 0.0
    total_ms: float = 0.0
    tokens_generated: int = 0
    tokens_per_second: float = 0.0
    tool_calls_made: int = 0


class StreamingGenerator:
    """Generates streaming responses from the LLM.

    Handles the connection to the LLM API, manages streaming state,
    and yields incremental tokens as they arrive.

    Example:
        generator = StreamingGenerator(settings)
        async for chunk in generator.stream(messages, tools=tool_schemas):
            print(chunk.delta, end="", flush=True)
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._client = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the LLM client."""
        if self._initialized:
            return

        try:
            from openai import AsyncOpenAI
            kwargs = {"api_key": self._settings.api_key}
            if self._settings.base_url:
                kwargs["base_url"] = self._settings.base_url
            self._client = AsyncOpenAI(**kwargs)
            self._initialized = True
            logger.info("StreamingGenerator initialized (provider=%s)", self._settings.provider)
        except ImportError:
            logger.error("openai package not installed")
        except Exception as exc:
            logger.error("Failed to initialize StreamingGenerator: %s", exc)

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from the LLM.

        Args:
            messages: Conversation messages in OpenAI format.
            tools: Tool schemas for function calling.
            model: Model override.
            temperature: Temperature override.
            max_tokens: Max tokens override.

        Yields:
            StreamChunk objects with incremental text.
        """
        if not self._initialized:
            await self.initialize()

        if not self._client:
            # Fallback: yield a placeholder
            yield StreamChunk(text="[LLM not available]", delta="[LLM not available]", finish_reason="error")
            return

        model = model or self._settings.model
        temperature = temperature if temperature is not None else self._settings.temperature
        max_tokens = max_tokens or self._settings.max_tokens

        start_time = time.perf_counter()
        first_token_time = 0.0
        full_text = ""
        all_tool_calls = []
        token_count = 0

        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await self._client.chat.completions.create(**kwargs)

            accumulated_tool_calls: dict[int, dict] = {}

            async for event in response:
                if not event.choices:
                    continue

                choice = event.choices[0]
                delta = choice.delta

                # Handle text content
                if delta.content:
                    if first_token_time == 0:
                        first_token_time = time.perf_counter() - start_time

                    full_text += delta.content
                    token_count += 1

                    yield StreamChunk(
                        text=full_text,
                        delta=delta.content,
                        index=choice.index,
                    )

                # Handle tool calls (streaming)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                # Handle finish
                if choice.finish_reason:
                    # Finalize tool calls
                    if accumulated_tool_calls:
                        all_tool_calls = list(accumulated_tool_calls.values())

                    yield StreamChunk(
                        text=full_text,
                        delta="",
                        finish_reason=choice.finish_reason,
                        tool_calls=all_tool_calls if all_tool_calls else None,
                        usage=getattr(event, "usage", None),
                        index=choice.index,
                    )

        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error("Streaming failed after %.1fms: %s", elapsed, exc)
            yield StreamChunk(
                text=full_text or f"[Error: {exc}]",
                delta=f"[Error: {exc}]",
                finish_reason="error",
            )

        # Log metrics
        total_ms = (time.perf_counter() - start_time) * 1000
        tps = token_count / (total_ms / 1000) if total_ms > 0 else 0

        logger.info(
            "Stream complete: %d tokens in %.0fms (%.1f tokens/s, first_token=%.0fms)",
            token_count,
            total_ms,
            tps,
            first_token_time * 1000,
        )

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, list[dict], StreamMetrics]:
        """Generate a complete response (non-streaming wrapper).

        Collects all streaming chunks into a final response.

        Args:
            messages: Conversation messages.
            tools: Tool schemas.
            model: Model override.
            temperature: Temperature override.
            max_tokens: Max tokens override.

        Returns:
            Tuple of (full_text, tool_calls, metrics).
        """
        metrics = StreamMetrics()
        start = time.perf_counter()
        first_token = 0.0
        full_text = ""
        all_tool_calls = []
        token_count = 0

        async for chunk in self.stream(messages, tools, model, temperature, max_tokens):
            if first_token == 0 and chunk.delta and chunk.finish_reason != "error":
                first_token = time.perf_counter() - start
                metrics.first_token_ms = first_token * 1000

            full_text = chunk.text
            token_count += 1

            if chunk.tool_calls:
                all_tool_calls = chunk.tool_calls

        metrics.total_ms = (time.perf_counter() - start) * 1000
        metrics.tokens_generated = token_count
        metrics.tokens_per_second = token_count / (metrics.total_ms / 1000) if metrics.total_ms > 0 else 0
        metrics.tool_calls_made = len(all_tool_calls)

        return full_text, all_tool_calls, metrics

    async def cleanup(self) -> None:
        """Release resources."""
        self._client = None
        self._initialized = False
