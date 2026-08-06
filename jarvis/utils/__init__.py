"""
JARVIS utilities package.
=========================
Provides logging setup, helper functions, and reusable decorators.

Quick Start:
    from jarvis.utils import get_logger, retry, Timer
"""

from jarvis.utils.logger import setup_logging, get_logger
from jarvis.utils.helpers import (
    utc_now,
    utc_timestamp,
    hash_text,
    ensure_directory,
    deep_merge,
    safe_json_loads,
    retry,
    Timer,
)
from jarvis.utils.decorators import log_execution, cache_result, require_features

__all__ = [
    "setup_logging",
    "get_logger",
    "utc_now",
    "utc_timestamp",
    "hash_text",
    "ensure_directory",
    "deep_merge",
    "safe_json_loads",
    "retry",
    "Timer",
    "log_execution",
    "cache_result",
    "require_features",
]
