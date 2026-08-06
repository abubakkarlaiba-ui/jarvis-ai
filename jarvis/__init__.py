"""
JARVIS AI Assistant
====================
J.A.R.V.I.S. — Just A Rather Very Intelligent System.

A production-ready desktop AI assistant with:
    - AI reasoning engine with streaming
    - Voice interaction (TTS/STT)
    - Comprehensive memory system
    - Vision and screen analysis
    - Desktop and browser automation
    - 15+ built-in skill plugins
    - Autonomous coding agent
    - Workflow execution engine
    - Enterprise-grade security
    - Performance optimization
    - Futuristic web UI

Architecture:
    - Async-first design throughout
    - Plugin-based skill system
    - FastAPI REST API
    - WebSocket real-time communication
    - Event-driven architecture

Quick Start:
    python -m jarvis

Usage:
    from jarvis.core.app import JARVIS
    jarvis = JARVIS()
    await jarvis.initialize()
    result = await jarvis.process("hello")
"""

__version__ = "2.0.0"
__author__ = "JARVIS Development Team"
