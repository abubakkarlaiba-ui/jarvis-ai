"""
JARVIS configuration package.
==============================
Provides validated settings and dependency injection.

Quick Start:
    from jarvis.config import get_settings, get_container
    settings = get_settings()
    container = get_container()
"""

from jarvis.config.settings import Settings, get_settings
from jarvis.config.dependency import Container, get_container

__all__ = ["Settings", "get_settings", "Container", "get_container"]
