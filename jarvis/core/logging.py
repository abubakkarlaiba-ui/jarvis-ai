import logging
import json
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Callable, Optional


class JarvisLogger:
    """Central logging system with rotation, formatting, and structured output."""

    def __init__(self, log_dir: str = "./logs", level: str = "INFO", json_output: bool = False):
        self.log_dir = log_dir
        self.level = level
        self.json_output = json_output
        self._log_entries: list[dict] = []
        self._callbacks: list[Callable] = []
        self._ensure_dirs()
        self.setup()

    def setup(self) -> None:
        """Configure root logger with handlers."""
        root = logging.getLogger()
        root.setLevel(getattr(logging, self.level.upper(), logging.INFO))

        for handler in root.handlers[:]:
            root.removeHandler(handler)

        root.addHandler(self._create_file_handler())
        root.addHandler(self._create_console_handler())

        if self.json_output:
            root.addHandler(self._create_json_handler())

    def get_logger(self, name: str) -> logging.Logger:
        """Get a named logger."""
        return logging.getLogger(name)

    def _create_file_handler(self) -> RotatingFileHandler:
        """Create rotating file handler (10MB, 5 backups)."""
        filepath = os.path.join(self.log_dir, "jarvis.log")
        handler = RotatingFileHandler(
            filepath, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(self._colored_formatter())
        return handler

    def _create_console_handler(self) -> logging.StreamHandler:
        """Create colored console handler."""
        handler = logging.StreamHandler()
        handler.setFormatter(self._colored_formatter())
        return handler

    def _create_json_handler(self) -> RotatingFileHandler:
        """Create JSON structured log handler."""
        filepath = os.path.join(self.log_dir, "jarvis_structured.json")
        handler = RotatingFileHandler(
            filepath, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(self._json_formatter())
        return handler

    def log_request(self, method: str, path: str, status: int, duration: float, user_id: str = None) -> None:
        """Log HTTP request."""
        logger = self.get_logger("jarvis.request")
        entry = {
            "type": "request",
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": round(duration * 1000, 2),
            "user_id": user_id,
        }
        self._store_entry(entry)
        logger.info(f"{method} {path} {status} {duration:.3f}s")

    def log_error(self, error: Exception, context: dict = None) -> None:
        """Log error with context."""
        logger = self.get_logger("jarvis.error")
        entry = {
            "type": "error",
            "error": type(error).__name__,
            "message": str(error),
            "context": context or {},
        }
        self._store_entry(entry)
        logger.error(f"{type(error).__name__}: {error}", exc_info=True)

    def log_performance(self, metric: str, value: float, tags: dict = None) -> None:
        """Log performance metric."""
        logger = self.get_logger("jarvis.performance")
        entry = {
            "type": "performance",
            "metric": metric,
            "value": value,
            "tags": tags or {},
        }
        self._store_entry(entry)
        logger.info(f"{metric}={value}")

    def log_security(self, action: str, user_id: str, success: bool, details: dict = None) -> None:
        """Log security event."""
        logger = self.get_logger("jarvis.security")
        entry = {
            "type": "security",
            "action": action,
            "user_id": user_id,
            "success": success,
            "details": details or {},
        }
        self._store_entry(entry)
        status = "OK" if success else "DENIED"
        logger.warning(f"SECURITY [{status}] {action} user={user_id}")

    def log_audit(self, action: str, user_id: str, resource: str, details: dict = None) -> None:
        """Log audit event."""
        logger = self.get_logger("jarvis.audit")
        entry = {
            "type": "audit",
            "action": action,
            "user_id": user_id,
            "resource": resource,
            "details": details or {},
        }
        self._store_entry(entry)
        logger.info(f"AUDIT {action} user={user_id} resource={resource}")

    def get_logs(self, level: str = None, count: int = 100) -> list[dict]:
        """Get recent logs."""
        logs = self._log_entries[-count:]
        if level:
            logs = [e for e in logs if e.get("level", "").upper() == level.upper()]
        return logs[-count:]

    def export_logs(self, format: str = "json") -> str:
        """Export logs."""
        if format == "json":
            return json.dumps(self._log_entries, indent=2, default=str)
        lines = []
        for e in self._log_entries:
            ts = e.get("timestamp", "")
            lvl = e.get("level", "")
            msg = e.get("message", e.get("type", ""))
            lines.append(f"{ts} | {lvl} | {msg}")
        return "\n".join(lines)

    def set_level(self, level: str) -> None:
        """Change log level."""
        self.level = level
        root = logging.getLogger()
        root.setLevel(getattr(logging, level.upper(), logging.INFO))

    def _json_formatter(self) -> logging.Formatter:
        """Create JSON formatter."""

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info and record.exc_info[1]:
                    log_data["exception"] = str(record.exc_info[1])
                return json.dumps(log_data, default=str)

        return JsonFormatter()

    def _colored_formatter(self) -> logging.Formatter:
        """Create colored formatter with ANSI codes."""

        class ColoredFormatter(logging.Formatter):
            COLORS = {
                "DEBUG": "\033[36m",
                "INFO": "\033[32m",
                "WARNING": "\033[33m",
                "ERROR": "\033[31m",
                "CRITICAL": "\033[35m",
            }
            RESET = "\033[0m"

            def format(self, record: logging.LogRecord) -> str:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                level = record.levelname
                color = self.COLORS.get(level, "")
                reset = self.RESET
                msg = record.getMessage()
                return f"{timestamp} | {color}{level:8}{reset} | {record.name} | {msg}"

        return ColoredFormatter()

    def _store_entry(self, entry: dict) -> None:
        """Store log entry in memory and notify callbacks."""
        entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
        entry["level"] = entry.get("type", "info").upper()
        self._log_entries.append(entry)
        if len(self._log_entries) > 10000:
            self._log_entries = self._log_entries[-5000:]
        for cb in self._callbacks:
            try:
                cb(entry)
            except Exception:
                pass

    def _ensure_dirs(self) -> None:
        """Ensure log directories exist."""
        os.makedirs(self.log_dir, exist_ok=True)
