"""
JARVIS API package.
===================
FastAPI-powered REST API for external integrations.

Quick Start:
    from jarvis.api import create_app
    app = create_app()
    # Run: uvicorn jarvis.api.app:app --host 0.0.0.0 --port 8000
"""

from jarvis.api.app import create_app, app, JarvisCore, get_jarvis_core

__all__ = ["create_app", "app", "JarvisCore", "get_jarvis_core"]
