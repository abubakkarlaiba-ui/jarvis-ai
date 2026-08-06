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

    Supports Google Gemini (free tier) and OpenAI-compatible APIs.
    """

    def __init__(self, settings: AISettings):
        self._settings = settings
        self._client = None
        self._gemini_model = None
        self._initialized = False
        self._provider = settings.provider

    async def initialize(self) -> None:
        """Initialize the LLM client."""
        if self._initialized:
            return

        # Try Gemini first (free tier available)
        if self._provider == "gemini" or (not self._provider and self._settings.api_key):
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._settings.api_key)
                self._gemini_model = genai.GenerativeModel(
                    model_name=self._settings.model or "gemini-2.0-flash",
                    generation_config=genai.GenerationConfig(
                        temperature=self._settings.temperature,
                        max_output_tokens=self._settings.max_tokens,
                    ),
                )
                self._initialized = True
                self._provider = "gemini"
                logger.info("StreamingGenerator initialized (provider=gemini, model=%s)", self._settings.model or "gemini-2.0-flash")
                return
            except ImportError:
                logger.warning("google-generativeai not installed, trying OpenAI")
            except Exception as exc:
                logger.warning("Failed to init Gemini: %s, trying OpenAI", exc)

        # Fallback to OpenAI
        try:
            from openai import AsyncOpenAI
            kwargs = {"api_key": self._settings.api_key}
            if self._settings.base_url:
                kwargs["base_url"] = self._settings.base_url
            self._client = AsyncOpenAI(**kwargs)
            self._initialized = True
            self._provider = "openai"
            logger.info("StreamingGenerator initialized (provider=openai)")
        except ImportError:
            logger.error("No LLM provider available (install google-generativeai or openai)")
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
        """Stream a response from the LLM."""
        if not self._initialized:
            await self.initialize()

        if not self._client and not self._gemini_model:
            yield StreamChunk(text="[LLM not available]", delta="[LLM not available]", finish_reason="error")
            return

        # Gemini streaming
        if self._provider == "gemini" and self._gemini_model:
            async for chunk in self._stream_gemini(messages, model, temperature, max_tokens):
                yield chunk
            return

        # OpenAI streaming
        async for chunk in self._stream_openai(messages, tools, model, temperature, max_tokens):
            yield chunk

    async def _stream_gemini(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream from Google Gemini."""
        import asyncio

        # Convert OpenAI message format to Gemini format
        system_msg = ""
        chat_history = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg += msg["content"] + "\n"
            elif msg["role"] == "user":
                chat_history.append({"role": "user", "parts": [msg["content"]]})
            elif msg["role"] == "assistant":
                chat_history.append({"role": "model", "parts": [msg["content"]]})

        # Prepend system message to first user message if exists
        if system_msg and chat_history:
            chat_history[0]["parts"][0] = system_msg + "\n" + chat_history[0]["parts"][0]
        elif system_msg:
            chat_history.append({"role": "user", "parts": [system_msg]})

        if not chat_history:
            yield StreamChunk(text="No input provided.", delta="No input provided.", finish_reason="stop")
            return

        try:
            # Use the model's generate_content with streaming
            response = self._gemini_model.generate_content(
                chat_history,
                stream=True,
            )

            full_text = ""
            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    yield StreamChunk(
                        text=full_text,
                        delta=chunk.text,
                        finish_reason=None,
                    )

            yield StreamChunk(
                text=full_text,
                delta="",
                finish_reason="stop",
            )

        except Exception as exc:
            logger.error("Gemini streaming error: %s", exc)
            yield StreamChunk(text=f"Error: {exc}", delta=f"Error: {exc}", finish_reason="error")

    async def _stream_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream from OpenAI-compatible API."""
        model = model or self._settings.model
        temperature = temperature if temperature is not None else self._settings.temperature
        max_tokens = max_tokens or self._settings.max_tokens

        full_text = ""
        all_tool_calls = []

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

                if delta.content:
                    full_text += delta.content
                    yield StreamChunk(text=full_text, delta=delta.content, index=choice.index)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {"id": tc.id or "", "type": "function", "function": {"name": "", "arguments": ""}}
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                if choice.finish_reason:
                    if accumulated_tool_calls:
                        all_tool_calls = list(accumulated_tool_calls.values())
                    yield StreamChunk(text=full_text, delta="", finish_reason=choice.finish_reason, tool_calls=all_tool_calls if all_tool_calls else None)

        except Exception as exc:
            logger.error("OpenAI streaming error: %s", exc)
            yield StreamChunk(text=f"Error: {exc}", delta=f"Error: {exc}", finish_reason="error")

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, list[dict], StreamMetrics]:
        """Generate a complete response (non-streaming wrapper)."""
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
        self._gemini_model = None
        self._initialized = False
