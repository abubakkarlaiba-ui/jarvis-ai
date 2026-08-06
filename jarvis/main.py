"""
JARVIS main entry point.
=======================
Provides CLI interface and application startup orchestration.

Usage:
    # Start the API server
    python -m jarvis.main --mode api

    # Start the terminal UI
    python -m jarvis.main --mode terminal

    # Start voice interaction (default)
    python -m jarvis.main --mode voice

    # Start everything
    python -m jarvis.main --mode all
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from jarvis.config import get_settings
from jarvis.utils.logger import setup_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS AI Assistant — Just A Rather Very Intelligent System",
    )
    parser.add_argument(
        "--mode",
        choices=["api", "terminal", "voice", "all"],
        default="voice",
        help="Run mode: api, terminal, voice, all (default: voice)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="API server host (overrides env)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="API server port (overrides env)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--list-mics",
        action="store_true",
        help="List available microphone devices and exit",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run microphone calibration before starting",
    )
    parser.add_argument(
        "--personality",
        default=None,
        help="TTS voice personality (jarvis, friday, friday_kid, british_butler)",
    )
    parser.add_argument(
        "--no-wake-word",
        action="store_true",
        help="Disable wake word detection (always listening for commands)",
    )
    return parser.parse_args()


async def run_api_server(host: str, port: int, debug: bool) -> None:
    """Start the FastAPI server using uvicorn."""
    import uvicorn

    config = uvicorn.Config(
        "jarvis.api.app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info("Starting API server on %s:%d", host, port)
    await server.serve()


async def run_terminal(brain) -> None:
    """Start the interactive terminal UI."""
    from jarvis.ui.terminal import TerminalUI
    ui = TerminalUI(brain)
    await ui.run()


async def run_voice(settings, args) -> None:
    """Start the voice interaction pipeline.

    Initializes the full voice system: microphone, VAD, STT, TTS,
    wake word detection, and conversation logging.

    Args:
        settings: Application settings.
        args: Parsed command-line arguments.
    """
    from jarvis.core.brain import BrainModule
    from jarvis.core.voice import VoicePipeline

    # Initialize brain for command processing
    brain = BrainModule()

    # Override settings from CLI
    voice_settings = settings.voice
    if args.no_wake_word:
        voice_settings.wake_word_enabled = False
    if args.personality:
        voice_settings.tts_personality = args.personality

    # Create and initialize pipeline
    pipeline = VoicePipeline(voice_settings)

    logger.info("Initializing voice pipeline...")
    await pipeline.initialize()

    # Calibrate if requested
    if args.calibrate:
        logger.info("Calibrating microphone... speak nothing for 3 seconds")
        success = await pipeline.calibrate(duration_seconds=3.0)
        if success:
            logger.info("Calibration complete — noise profile learned")
        else:
            logger.warning("Calibration failed — continuing without noise profile")

    # Define command handler
    async def handle_command(text: str) -> str:
        """Process a voice command through the Brain module."""
        response = await brain.process(text)
        return response.text

    print("\n  J.A.R.V.I.S. Voice System Online")
    print("  Say 'Hey Jarvis' to begin, or speak a command.\n")

    # Run the pipeline
    await pipeline.run(command_handler=handle_command)


def list_microphones() -> None:
    """List all available microphone devices."""
    from jarvis.core.voice import MicrophoneManager

    print("\n  Available Microphone Devices\n")
    print("  Index | Channels | Sample Rate | Name")
    print("  " + "-" * 60)

    devices = MicrophoneManager.list_devices()
    if not devices:
        print("  No microphone devices found.")
        return

    for dev in devices:
        default = " *" if dev.is_default else ""
        print(f"  {dev.index:>5} | {dev.channels:>8} | {dev.sample_rate:>10} | {dev.name}{default}")

    print("\n  * = default device")
    print(f"\n  Use --mic-device <index> in .env to select a device.\n")


async def main_async(args: argparse.Namespace) -> None:
    """Main async entry point."""
    settings = get_settings()

    setup_logging(
        level="DEBUG" if args.debug else settings.logging.level,
        log_file=settings.logging.file_path,
        console_output=settings.logging.console_output,
    )

    logger.info("JARVIS v%s initializing...", settings.version)

    # Handle list-mics
    if args.list_mics:
        list_microphones()
        return

    # Initialize core modules
    from jarvis.core.brain import BrainModule
    from jarvis.core.memory import MemoryModule

    brain = BrainModule()
    memory = MemoryModule(settings.memory)

    host = args.host or settings.api.host
    port = args.port or settings.api.port

    tasks = []

    if args.mode in ("api", "all"):
        tasks.append(run_api_server(host, port, args.debug))

    if args.mode in ("terminal", "all"):
        tasks.append(run_terminal(brain))

    if args.mode in ("voice", "all"):
        await run_voice(settings, args)
        return  # Voice mode blocks until shutdown

    if tasks:
        await asyncio.gather(*tasks)
    else:
        logger.warning("No run mode selected. Use --mode api|terminal|voice|all")


def main() -> None:
    """Synchronous entry point wrapping the async main function."""
    args = parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nJARVIS shutting down. Goodbye, sir.")
        sys.exit(0)


if __name__ == "__main__":
    main()
