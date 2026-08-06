"""
Terminal UI module — text-based interface for JARVIS.
====================================================
Provides a rich terminal interface for interacting with JARVIS
when a graphical UI is not available.

Usage:
    terminal = TerminalUI()
    await terminal.run()
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jarvis.core.brain import BrainModule
    from jarvis.core.voice import VoiceModule

logger = logging.getLogger(__name__)


class TerminalUI:
    """Text-based terminal interface for JARVIS.

    Reads user input from stdin, sends it to the Brain module,
    and prints responses to stdout.

    Example:
        ui = TerminalUI(brain)
        await ui.run()
    """

    BANNER = """
    ╔═══════════════════════════════════════════╗
    ║           J.A.R.V.I.S. Terminal           ║
    ║   Just A Rather Very Intelligent System   ║
    ╚═══════════════════════════════════════════╝
    Type 'exit' or 'quit' to leave.
    Type 'help' for available commands.
    """

    HELP_TEXT = """
    Available commands:
      exit / quit    — Exit JARVIS
      clear          — Clear conversation history
      status         — Show system status
      skills         — List installed skills
      memory         — Show memory statistics
      help           — Show this help message
    """

    def __init__(self, brain: BrainModule | None = None):
        self.brain = brain
        self._running = False

    async def run(self) -> None:
        """Start the interactive terminal loop."""
        print(self.BANNER)
        self._running = True

        while self._running:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("\033[96mJARVIS ▸ \033[0m")
                )
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye, sir.")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                print("Shutting down JARVIS. Goodbye, sir.")
                self._running = False
                break

            await self._handle_command(user_input)

    async def _handle_command(self, user_input: str) -> None:
        """Route user input to the appropriate handler."""
        command = user_input.lower()

        if command == "help":
            print(self.HELP_TEXT)
        elif command == "clear":
            if self.brain:
                self.brain.context_manager.clear()
            print("Conversation history cleared.")
        elif command == "status":
            print("JARVIS is operational.")
        elif command == "skills":
            print("Skills management available via API at /skills/")
        elif command == "memory":
            print("Memory statistics available via API at /memory/stats")
        else:
            await self._process_query(user_input)

    async def _process_query(self, text: str) -> None:
        """Send text to the Brain module and display the response."""
        if not self.brain:
            print("Brain module not connected.")
            return

        response = await self.brain.process(text)
        print(f"\n\033[93m{response.text}\033[0m")
