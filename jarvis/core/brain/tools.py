"""
Tool calling system for the JARVIS reasoning engine.
====================================================
Enables the LLM to call external tools (functions) during reasoning.

Tools are registered as Python callables with JSON schema definitions.
The reasoning engine decides when to invoke a tool, executes it, and
feeds the result back into the conversation.

This implements the OpenAI function calling pattern with extensions:
    - Parallel tool calls (multiple tools in one turn)
    - Tool call chaining (output of one feeds into the next)
    - Timeout and error handling per tool
    - Usage tracking and rate limiting

Usage:
    registry = ToolRegistry()
    registry.register(get_weather, description="Get current weather", parameters={...})
    result = await registry.execute("get_weather", {"city": "London"})
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional

from jarvis.config.settings import AISettings

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Categories of tools for organization and access control."""
    INFORMATION = auto()
    AUTOMATION = auto()
    FILE_SYSTEM = auto()
    WEB = auto()
    SYSTEM = auto()
    CUSTOM = auto()


@dataclass
class ToolParameter:
    """Schema definition for a tool parameter."""
    name: str
    type: str  # string, number, boolean, array, object
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[Any] | None = None

    def to_schema(self) -> dict:
        schema: dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class ToolDefinition:
    """Complete definition of a callable tool."""
    name: str
    description: str
    parameters: list[ToolParameter]
    category: ToolCategory = ToolCategory.CUSTOM
    handler: Callable | None = None
    timeout_seconds: float = 30.0
    requires_auth: bool = False
    enabled: bool = True
    call_count: int = 0
    last_called: float = 0.0

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []
        for param in self.parameters:
            properties[param.name] = param.to_schema()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: Any = None
    error: str = ""
    tool_name: str = ""
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """Registry of all available tools for the reasoning engine.

    Tools are registered with schemas and handlers. The reasoning engine
    queries this registry to know what tools are available and to execute
    tool calls.

    Example:
        registry = ToolRegistry()

        @registry.tool(
            name="get_weather",
            description="Get current weather for a city",
            parameters=[
                ToolParameter("city", "string", "City name", required=True),
            ],
        )
        async def get_weather(city: str) -> dict:
            return {"temp": 22, "condition": "sunny"}
    """

    def __init__(self, settings: AISettings | None = None):
        self._settings = settings
        self._tools: dict[str, ToolDefinition] = {}
        self._max_calls = settings.max_tool_calls_per_turn if settings else 5
        self._calls_this_turn = 0
        self._turn_start = 0.0

        # Register built-in tools
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in system tools."""
        self.register(
            name="system_info",
            description="Get current system information (time, date, platform)",
            handler=self._builtin_system_info,
            parameters=[],
            category=ToolCategory.SYSTEM,
        )

        self.register(
            name="remember",
            description="Store a fact in long-term memory for future recall",
            handler=self._builtin_remember,
            parameters=[
                ToolParameter("content", "string", "The fact or information to remember"),
                ToolParameter("category", "string", "Category label", required=False, default="general"),
            ],
            category=ToolCategory.CUSTOM,
        )

        self.register(
            name="recall",
            description="Search long-term memory for previously stored information",
            handler=self._builtin_recall,
            parameters=[
                ToolParameter("query", "string", "Search query"),
            ],
            category=ToolCategory.CUSTOM,
        )

    def register(
        self,
        name: str,
        description: str,
        handler: Callable,
        parameters: list[ToolParameter] | None = None,
        category: ToolCategory = ToolCategory.CUSTOM,
        timeout: float = 30.0,
    ) -> ToolDefinition:
        """Register a new tool.

        Args:
            name: Unique tool name.
            description: Human-readable description.
            handler: Async or sync callable that implements the tool.
            parameters: Parameter schema definitions.
            category: Tool category.
            timeout: Execution timeout in seconds.

        Returns:
            The created ToolDefinition.
        """
        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters or [],
            category=category,
            handler=handler,
            timeout_seconds=timeout,
        )
        self._tools[name] = tool
        logger.debug("Registered tool: %s (%s)", name, category.name)
        return tool

    def tool(
        self,
        name: str,
        description: str,
        parameters: list[ToolParameter] | None = None,
        category: ToolCategory = ToolCategory.CUSTOM,
        timeout: float = 30.0,
    ) -> Callable:
        """Decorator to register a function as a tool.

        Usage:
            @registry.tool("get_weather", "Get weather for a city", [...])
            async def get_weather(city: str) -> dict: ...
        """
        def decorator(func: Callable) -> Callable:
            self.register(name, description, func, parameters, category, timeout)
            return func
        return decorator

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with the given arguments.

        Args:
            name: Tool name.
            arguments: Tool arguments as a dictionary.

        Returns:
            ToolResult with the execution outcome.
        """
        # Rate limiting
        if self._calls_this_turn >= self._max_calls:
            return ToolResult(
                success=False,
                error=f"Tool call limit reached ({self._max_calls} per turn)",
                tool_name=name,
            )

        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {name}",
                tool_name=name,
            )

        if not tool.enabled:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' is disabled",
                tool_name=name,
            )

        if not tool.handler:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' has no handler",
                tool_name=name,
            )

        # Execute with timeout
        start = time.perf_counter()
        self._calls_this_turn += 1
        tool.call_count += 1
        tool.last_called = time.monotonic()

        try:
            if asyncio.iscoroutinefunction(tool.handler):
                result = await asyncio.wait_for(
                    tool.handler(**arguments),
                    timeout=tool.timeout_seconds,
                )
            else:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool.handler(**arguments)),
                    timeout=tool.timeout_seconds,
                )

            elapsed = (time.perf_counter() - start) * 1000

            # Convert result to string if needed
            if isinstance(result, dict):
                output = json.dumps(result, default=str)
            elif not isinstance(result, str):
                output = str(result)
            else:
                output = result

            logger.info("Tool '%s' executed in %.1fms", name, elapsed)

            return ToolResult(
                success=True,
                output=output,
                tool_name=name,
                execution_time_ms=elapsed,
            )

        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Tool '%s' timed out after %.1fs", name, tool.timeout_seconds)
            return ToolResult(
                success=False,
                error=f"Tool '{name}' timed out after {tool.timeout_seconds}s",
                tool_name=name,
                execution_time_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Tool '%s' failed: %s", name, exc)
            return ToolResult(
                success=False,
                error=f"Tool '{name}' failed: {str(exc)}",
                tool_name=name,
                execution_time_ms=elapsed,
            )

    def get_schemas(self, category: ToolCategory | None = None) -> list[dict]:
        """Get OpenAI-compatible schemas for all tools.

        Args:
            category: Filter by category, or None for all.

        Returns:
            List of tool schemas.
        """
        schemas = []
        for tool in self._tools.values():
            if not tool.enabled:
                continue
            if category and tool.category != category:
                continue
            schemas.append(tool.to_openai_schema())
        return schemas

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        """Return metadata for all registered tools."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category.name,
                "enabled": t.enabled,
                "call_count": t.call_count,
                "parameters": len(t.parameters),
            }
            for t in self._tools.values()
        ]

    def enable_tool(self, name: str) -> bool:
        if name in self._tools:
            self._tools[name].enabled = True
            return True
        return False

    def disable_tool(self, name: str) -> bool:
        if name in self._tools:
            self._tools[name].enabled = False
            return True
        return False

    def reset_turn_counter(self) -> None:
        """Reset the per-turn call counter (call at the start of each turn)."""
        self._calls_this_turn = 0
        self._turn_start = time.monotonic()

    # ── Built-in tool handlers ───────────────────────────────────────

    async def _builtin_system_info(self) -> dict:
        """Return current system information."""
        from jarvis.utils.helpers import utc_now
        now = utc_now()
        return {
            "time": now.strftime("%H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "day": now.strftime("%A"),
            "timezone": "UTC",
        }

    async def _builtin_remember(self, content: str, category: str = "general") -> str:
        """Store a fact in long-term memory."""
        # This will be wired to the memory system by the orchestrator
        return f"Remembered: '{content}' (category: {category})"

    async def _builtin_recall(self, query: str) -> str:
        """Search long-term memory."""
        # This will be wired to the memory system by the orchestrator
        return f"Searching memory for: '{query}'"
