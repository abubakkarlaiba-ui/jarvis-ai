"""
JARVIS Core — unified command router.
======================================
Routes user commands to the appropriate subsystem module.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class Command:
    """A parsed user command."""
    raw: str = ""
    intent: str = ""
    action: str = ""
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class CommandResult:
    """Result of processing a command."""
    success: bool = True
    output: Any = None
    message: str = ""
    module: str = ""
    action: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""


# ── Intent patterns ───────────────────────────────────────────────

INTENT_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # Chat / Conversation
    ("chat", "message", re.compile(
        r"^(hello|hi|hey|good morning|good evening|how are you|what'?s up)",
        re.IGNORECASE,
    )),
    # Skills
    ("skill", "execute", re.compile(
        r"^(run|execute|use|invoke|call)\s+(?:the\s+)?(\w+)(?:\s+skill)?",
        re.IGNORECASE,
    )),
    ("skill", "list", re.compile(
        r"^(list|show|what)\s+(?:all\s+)?(?:the\s+)?skills?",
        re.IGNORECASE,
    )),
    ("skill", "install", re.compile(
        r"^(install|add|add)\s+(?:a\s+)?skill",
        re.IGNORECASE,
    )),
    # Memory
    ("memory", "search", re.compile(
        r"^(search|find|look up|recall|remember)\s+(?:in\s+)?(?:my\s+)?(?:memory|notes?)",
        re.IGNORECASE,
    )),
    ("memory", "store", re.compile(
        r"^(remember|store|save|note)\s+(?:that\s+)?",
        re.IGNORECASE,
    )),
    ("memory", "forget", re.compile(
        r"^(forget|delete|remove)\s+(?:from\s+)?(?:my\s+)?(?:memory|notes?)",
        re.IGNORECASE,
    )),
    # Workflow
    ("workflow", "execute", re.compile(
        r"^(run|execute|start|do)\s+(?:the\s+)?(?:task|workflow|job)",
        re.IGNORECASE,
    )),
    ("workflow", "create", re.compile(
        r"^(create|make|build)\s+(?:a\s+)?(?:new\s+)?(?:task|workflow|plan)",
        re.IGNORECASE,
    )),
    ("workflow", "status", re.compile(
        r"^(check|show|get|what'?s)\s+(?:the\s+)?(?:task|workflow|job)\s*(?:status)?",
        re.IGNORECASE,
    )),
    # Coding
    ("coding", "generate", re.compile(
        r"^(generate|create|write|build)\s+(?:a\s+)?(?:new\s+)?(?:code|function|class|api|endpoint)",
        re.IGNORECASE,
    )),
    ("coding", "explain", re.compile(
        r"^(explain|describe|what)\s+(?:does\s+)?(?:this\s+)?(?:code|function|class)",
        re.IGNORECASE,
    )),
    ("coding", "debug", re.compile(
        r"^(debug|fix|debug)\s+(?:this\s+)?(?:code|bug|error)",
        re.IGNORECASE,
    )),
    ("coding", "test", re.compile(
        r"^(run|execute)\s+(?:the\s+)?tests?",
        re.IGNORECASE,
    )),
    ("coding", "git", re.compile(
        r"^(git|commit|push|pull|status)\s*",
        re.IGNORECASE,
    )),
    # Vision
    ("vision", "screenshot", re.compile(
        r"^(take|capture)\s+(?:a\s+)?screenshot",
        re.IGNORECASE,
    )),
    ("vision", "analyze", re.compile(
        r"^(analyze|look at|read|scan)\s+(?:this\s+)?(?:image|screenshot|picture|photo)",
        re.IGNORECASE,
    )),
    ("vision", "ocr", re.compile(
        r"^(read|extract|get)\s+(?:the\s+)?(?:text|ocr)\s*(?:from)?",
        re.IGNORECASE,
    )),
    # System
    ("system", "status", re.compile(
        r"^(system|status|health|how)?\s*(?:is\s+)?(?:everything|system|health)",
        re.IGNORECASE,
    )),
    ("system", "info", re.compile(
        r"^(show|get|what)?\s*(?:system|computer|machine)\s*(?:info|information|stats|status)?",
        re.IGNORECASE,
    )),
    # Security
    ("security", "login", re.compile(
        r"^(log\s*in|sign\s*in|authenticate)",
        re.IGNORECASE,
    )),
    ("security", "logout", re.compile(
        r"^(log\s*out|sign\s*out)",
        re.IGNORECASE,
    )),
    # Performance
    ("performance", "report", re.compile(
        r"^(show|get|generate)\s+(?:a\s+)?(?:performance|perf|benchmark)\s*report?",
        re.IGNORECASE,
    )),
    ("performance", "cache", re.compile(
        r"^(clear|show|flush)\s+(?:the\s+)?cache",
        re.IGNORECASE,
    )),
    # Backup
    ("backup", "create", re.compile(
        r"^(create|make|run)\s+(?:a\s+)?backup",
        re.IGNORECASE,
    )),
    ("backup", "restore", re.compile(
        r"^(restore|recover)\s+(?:from\s+)?backup",
        re.IGNORECASE,
    )),
    # Update
    ("update", "check", re.compile(
        r"^(check|are there)\s+(?:for\s+)?updates?",
        re.IGNORECASE,
    )),
    # Help
    ("help", "general", re.compile(
        r"^(help|assist|what can you do|commands|options)",
        re.IGNORECASE,
    )),
]


class CommandRouter:
    """Unified command router that dispatches to subsystems.

    Parses natural language commands, determines intent and action,
    and routes to the appropriate handler.
    """

    def __init__(self):
        self._handlers: dict[str, dict[str, Callable]] = {}
        self._fallback: Callable | None = None
        self._middleware: list[Callable] = []
        self._command_history: list[Command] = []
        self._max_history = 100

    # ── Registration ──────────────────────────────────────────────

    def register(self, module: str, action: str, handler: Callable) -> None:
        """Register a command handler."""
        if module not in self._handlers:
            self._handlers[module] = {}
        self._handlers[module][action] = handler
        logger.debug("Registered handler: %s.%s", module, action)

    def register_fallback(self, handler: Callable) -> None:
        """Register a fallback handler for unmatched commands."""
        self._fallback = handler

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware that runs before every command."""
        self._middleware.append(middleware)

    # ── Parsing ───────────────────────────────────────────────────

    def parse(self, raw_input: str) -> Command:
        """Parse raw user input into a Command object."""
        raw = raw_input.strip()
        if not raw:
            return Command(raw="")

        for intent, action, pattern in INTENT_PATTERNS:
            match = pattern.search(raw)
            if match:
                params = {}
                groups = match.groups()
                if len(groups) > 1:
                    params["target"] = groups[1]
                elif len(groups) == 1 and groups[0]:
                    params["target"] = groups[0]

                return Command(
                    raw=raw,
                    intent=intent,
                    action=action,
                    target=params.get("target", ""),
                    parameters=params,
                    confidence=0.9,
                )

        # Fallback: treat as chat
        return Command(
            raw=raw,
            intent="chat",
            action="message",
            target=raw,
            parameters={"message": raw},
            confidence=0.5,
        )

    # ── Routing ───────────────────────────────────────────────────

    async def route(self, raw_input: str, context: dict | None = None) -> CommandResult:
        """Route a user command to the appropriate handler.

        Args:
            raw_input: Raw user input string.
            context: Optional context (user_id, session, etc.)

        Returns:
            CommandResult with the handler's output.
        """
        command = self.parse(raw_input)
        self._command_history.append(command)
        if len(self._command_history) > self._max_history:
            self._command_history.pop(0)

        if not command.intent:
            return CommandResult(
                success=False,
                error="Could not understand command",
                module="router",
            )

        # Run middleware
        for mw in self._middleware:
            try:
                result = await mw(command, context)
                if result is False:
                    return CommandResult(
                        success=False,
                        error="Command blocked by middleware",
                        module="router",
                    )
            except Exception as e:
                logger.warning("Middleware error: %s", e)

        # Find handler
        handler = self._handlers.get(command.intent, {}).get(command.action)
        if handler is None:
            # Try intent-only match
            handlers = self._handlers.get(command.intent, {})
            if handlers:
                handler = next(iter(handlers.values()), None)

        if handler is None:
            if self._fallback:
                handler = self._fallback
            else:
                return CommandResult(
                    success=False,
                    error=f"No handler for: {command.intent}.{command.action}",
                    module="router",
                    metadata={"command": vars(command)},
                )

        # Execute handler
        try:
            if hasattr(handler, "__call__"):
                import inspect
                sig = inspect.signature(handler)
                if len(sig.parameters) >= 2:
                    result = await handler(command, context or {})
                elif len(sig.parameters) == 1:
                    result = await handler(command)
                else:
                    result = await handler()
            else:
                result = await handler(command)

            if isinstance(result, CommandResult):
                result.module = command.intent
                result.action = command.action
                return result

            return CommandResult(
                success=True,
                output=result,
                module=command.intent,
                action=command.action,
            )

        except Exception as e:
            logger.error("Handler error: %s.%s: %s", command.intent, command.action, e)
            return CommandResult(
                success=False,
                error=str(e),
                module=command.intent,
                action=command.action,
            )

    # ── History ───────────────────────────────────────────────────

    def get_history(self, count: int = 10) -> list[Command]:
        return self._command_history[-count:]

    def get_stats(self) -> dict:
        intents = {}
        for cmd in self._command_history:
            intents[cmd.intent] = intents.get(cmd.intent, 0) + 1
        return {
            "total_commands": len(self._command_history),
            "by_intent": intents,
            "registered_handlers": sum(
                len(h) for h in self._handlers.values()
            ),
        }
