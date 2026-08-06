"""JARVIS Installation Wizard — First-time setup."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
          Just A Rather Very Intelligent System
"""

REQUIRED_DIRS = [
    "data",
    "data/config",
    "data/memory",
    "data/security",
    "data/backups",
    "logs",
    "plugins",
]

DEFAULTS: dict[str, Any] = {
    "openai_api_key": "",
    "model": "gpt-4o",
    "voice_enabled": True,
    "tts_engine": "pyttsx3",
    "admin_password": "admin",
    "enable_2fa": False,
    "auto_backup_hours": 24,
}


def _check_python() -> None:
    if sys.version_info < (3, 10):
        print(f"[ERROR] Python 3.10+ required. Found {sys.version}.")
        sys.exit(1)
    print(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor}")


def _install_deps() -> None:
    req = Path(__file__).resolve().parents[2] / "requirements.txt"
    if not req.exists():
        print("[WARN] requirements.txt not found — skipping.")
        return
    print("[INFO] Installing dependencies …")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(req)],
        stdout=subprocess.DEVNULL,
    )
    print("[OK] Dependencies installed.")


def _create_dirs(project: Path) -> None:
    for d in REQUIRED_DIRS:
        (project / d).mkdir(parents=True, exist_ok=True)
    print("[OK] Directory structure created.")


def _prompt(key: str, default: Any, label: str) -> Any:
    raw = input(f"  {label} [{default}]: ").strip()
    if raw == "":
        return default
    if isinstance(default, bool):
        return raw.lower() in ("y", "yes", "true", "1")
    if isinstance(default, int):
        try:
            return int(raw)
        except ValueError:
            return default
    return raw


def _write_config(project: Path, cfg: dict[str, Any]) -> None:
    cfg_path = project / "data" / "config" / "jarvis.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"[OK] Config written to {cfg_path}")


def _write_env(project: Path, api_key: str) -> None:
    env_path = project / ".env"
    content = f"OPENAI_API_KEY={api_key}\n"
    env_path.write_text(content, encoding="utf-8")
    print(f"[OK] .env written to {env_path}")


def run_setup() -> None:
    """Main entry point — runs the interactive wizard."""
    try:
        print(BANNER)
        print("Welcome to the JARVIS installer.\n")

        _check_python()

        project = Path(__file__).resolve().parents[2]

        _install_deps()
        _create_dirs(project)

        print("\n--- AI Model Configuration ---")
        api_key = _prompt("openai_api_key", DEFAULTS["openai_api_key"], "OpenAI API key")
        model = _prompt("model", DEFAULTS["model"], "Model name")

        print("\n--- Voice Settings ---")
        voice_enabled = _prompt("voice_enabled", DEFAULTS["voice_enabled"], "Enable voice? (y/n)")
        tts_engine = _prompt("tts_engine", DEFAULTS["tts_engine"], "TTS engine")

        print("\n--- Security Settings ---")
        admin_pw = _prompt("admin_password", DEFAULTS["admin_password"], "Admin password")
        enable_2fa = _prompt("enable_2fa", DEFAULTS["enable_2fa"], "Enable 2FA? (y/n)")

        print("\n--- Backup Settings ---")
        backup_hours = _prompt("auto_backup_hours", DEFAULTS["auto_backup_hours"], "Backup interval (hours)")

        cfg = {
            "ai": {"api_key": api_key, "model": model},
            "voice": {"enabled": voice_enabled, "engine": tts_engine},
            "security": {"admin_password": admin_pw, "enable_2fa": enable_2fa},
            "backup": {"auto_backup_hours": backup_hours},
        }

        _write_config(project, cfg)
        _write_env(project, api_key)

        print("\n========================================")
        print(" JARVIS setup complete!")
        print("========================================")
        print("Next steps:")
        print("  1. Run  jarvis          — start the assistant")
        print("  2. Run  jarvis serve    — start the API server")
        print("  3. Edit data/config/jarvis.json to tweak settings")

    except KeyboardInterrupt:
        print("\n[INFO] Setup cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    run_setup()
