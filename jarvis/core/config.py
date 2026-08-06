import json
import os
import copy
from typing import Any, Callable


class JarvisConfig:
    """Centralized configuration management with env vars, JSON files, and defaults."""

    def __init__(self, config_dir: str = "./data/config", env_prefix: str = "JARVIS_"):
        self.config_dir = config_dir
        self.env_prefix = env_prefix
        self._config: dict = {}
        self._callbacks: list[Callable] = []
        self._ensure_dirs()
        self.load()

    def load(self) -> None:
        """Load configuration from files and env vars."""
        defaults = self._load_defaults()
        local = self._load_file("local.json")
        user = self._load_file("user.json")
        env = self._load_env()
        self._config = self._merge(defaults, local, user, env)

    def _load_defaults(self) -> dict:
        """Load default configuration."""
        return {
            "ai": {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 4096,
                "provider": "openai",
                "fallback_model": "gpt-3.5-turbo",
                "embedding_model": "text-embedding-ada-002",
            },
            "voice": {
                "enabled": True,
                "engine": "pyttsx3",
                "language": "en-US",
                "rate": 150,
                "volume": 0.8,
                "wake_word": "jarvis",
                "noise_threshold": 0.5,
                "sample_rate": 16000,
            },
            "memory": {
                "enabled": True,
                "backend": "sqlite",
                "max_entries": 10000,
                "embedding_cache": True,
                "auto_summarize": True,
                "retention_days": 90,
            },
            "skills": {
                "auto_discover": True,
                "max_concurrent": 5,
                "timeout": 30,
                "cache_enabled": True,
            },
            "security": {
                "enabled": True,
                "require_auth": False,
                "max_attempts": 5,
                "lockout_duration": 300,
                "allowed_origins": ["*"],
                "rate_limit": 100,
            },
            "performance": {
                "max_workers": 4,
                "cache_size": 1000,
                "profiling": False,
                "metrics_interval": 60,
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8000,
                "debug": False,
                "cors": True,
                "version": "1.0.0",
            },
            "logging": {
                "level": "INFO",
                "json_output": False,
                "log_dir": "./logs",
                "max_size_mb": 10,
                "backups": 5,
            },
            "backup": {
                "enabled": False,
                "interval_hours": 24,
                "retention_days": 30,
                "directory": "./backups",
            },
            "vision": {
                "enabled": False,
                "camera_index": 0,
                "capture_interval": 1.0,
                "resolution": [640, 480],
            },
            "automation": {
                "enabled": False,
                "schedules": [],
                "max_concurrent": 3,
            },
            "browser": {
                "enabled": False,
                "headless": True,
                "timeout": 30,
                "user_agent": None,
            },
            "coding": {
                "enabled": False,
                "auto_format": True,
                "lint_on_save": True,
                "max_line_length": 120,
            },
            "workflow": {
                "enabled": False,
                "auto_save": True,
                "max_steps": 100,
                "retry_on_failure": True,
            },
        }

    def _load_file(self, filename: str) -> dict:
        """Load from JSON file."""
        filepath = os.path.join(self.config_dir, filename)
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _load_env(self) -> dict:
        """Load from environment variables with prefix."""
        result = {}
        for key, value in os.environ.items():
            if key.startswith(self.env_prefix):
                parts = key[len(self.env_prefix) :].lower().split("_")
                current = result
                for part in parts[:-1]:
                    current = current.setdefault(part, {})
                final_key = parts[-1]
                try:
                    current[final_key] = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    current[final_key] = value
        return result

    def _merge(self, *dicts) -> dict:
        """Deep merge configuration dictionaries."""
        result = {}
        for d in dicts:
            if not isinstance(d, dict):
                continue
            for key, value in d.items():
                if (
                    key in result
                    and isinstance(result[key], dict)
                    and isinstance(value, dict)
                ):
                    result[key] = self._merge(result[key], value)
                else:
                    result[key] = copy.deepcopy(value)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with dot notation (ai.model)."""
        parts = key.split(".")
        current = self._config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return copy.deepcopy(current)

    def set(self, key: str, value: Any) -> None:
        """Set config value."""
        parts = key.split(".")
        current = self._config
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        old_value = current.get(parts[-1])
        current[parts[-1]] = value
        if old_value != value:
            self._notify_callbacks(key, value, old_value)

    def get_section(self, section: str) -> dict:
        """Get a section of config."""
        return copy.deepcopy(self._config.get(section, {}))

    def save(self) -> None:
        """Save current config to file."""
        filepath = os.path.join(self.config_dir, "user.json")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, default=str)

    def reset(self) -> None:
        """Reset to defaults."""
        self._config = self._load_defaults()
        filepath = os.path.join(self.config_dir, "user.json")
        if os.path.exists(filepath):
            os.remove(filepath)

    def validate(self) -> list[str]:
        """Validate config, return list of errors."""
        errors = []
        port = self.get("api.port")
        if not isinstance(port, int) or not (1 <= port <= 65535):
            errors.append(f"Invalid API port: {port}")
        level = self.get("logging.level", "").upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            errors.append(f"Invalid log level: {level}")
        temp = self.get("ai.temperature")
        if temp is not None and not (0.0 <= temp <= 2.0):
            errors.append(f"Invalid temperature: {temp}")
        rate = self.get("voice.rate")
        if rate is not None and not (50 <= rate <= 500):
            errors.append(f"Invalid voice rate: {rate}")
        if self.get("security.rate_limit") is not None:
            if self.get("security.rate_limit") < 0:
                errors.append("Rate limit must be non-negative")
        return errors

    def get_all(self) -> dict:
        """Get all config values."""
        return copy.deepcopy(self._config)

    def _ensure_dirs(self) -> None:
        """Create config directories."""
        os.makedirs(self.config_dir, exist_ok=True)

    def watch(self, callback: Callable) -> None:
        """Register config change callback."""
        self._callbacks.append(callback)

    def _notify_callbacks(self, key: str, new_value: Any, old_value: Any) -> None:
        """Notify registered callbacks of config changes."""
        for cb in self._callbacks:
            try:
                cb(key, new_value, old_value)
            except Exception:
                pass
