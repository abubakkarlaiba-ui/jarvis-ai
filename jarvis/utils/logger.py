"""
Logging utilities for JARVIS.
============================
Provides a centralized, configurable logging setup with rotating file handlers.

Usage:
    from jarvis.utils.logger import setup_logging, get_logger
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Application started")
"""

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_format: str | None = None,
    log_file: str | None = None,
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
    console_output: bool = True,
) -> None:
    """Configure the root logger for the entire application.

    Args:
        level: Logging level as a string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Custom format string. Uses a default if None.
        log_file: Path to the log file. If None, only console output is used.
        max_bytes: Maximum size per log file before rotation.
        backup_count: Number of rotated log files to keep.
        console_output: Whether to also log to stderr.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        log_format or "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger.handlers.clear()

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    if console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A configured Logger instance.
    """
    return logging.getLogger(name)
