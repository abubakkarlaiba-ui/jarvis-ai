"""
JARVIS core package.
===================
Contains the core modules: Brain, Voice, Memory, Vision, Automation, Skills,
Workflow, Coding, Security, Performance, and the unified CommandRouter.

Quick Start:
    from jarvis.core.app import JARVIS
    jarvis = JARVIS()
    await jarvis.initialize()
    result = await jarvis.process("hello")
"""

from jarvis.core.app import JARVIS, get_jarvis
from jarvis.core.config import JarvisConfig
from jarvis.core.logging import JarvisLogger
from jarvis.core.router import CommandRouter, Command, CommandResult

__all__ = [
    "JARVIS",
    "get_jarvis",
    "JarvisConfig",
    "JarvisLogger",
    "CommandRouter",
    "Command",
    "CommandResult",
]
