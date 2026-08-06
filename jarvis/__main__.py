"""
JARVIS — Entry point.
====================
Run with: python -m jarvis
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="J.A.R.V.I.S. — Just A Rather Very Intelligent System",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="API server host (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="API server port (default: 8000)"
    )
    parser.add_argument(
        "--data-dir", default="./data", help="Data directory (default: ./data)"
    )
    parser.add_argument(
        "--config", default=None, help="Config file path"
    )
    parser.add_argument(
        "--no-api", action="store_true", help="Disable API server"
    )
    parser.add_argument(
        "--no-ui", action="store_true", help="Disable UI"
    )
    parser.add_argument(
        "--setup", action="store_true", help="Run installation wizard"
    )
    parser.add_argument(
        "--version", action="version", version="JARVIS 2.0.0"
    )
    return parser.parse_args()


async def run_server(jarvis, host: str, port: int, no_ui: bool) -> None:
    """Run the FastAPI server with uvicorn."""
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Run: pip install uvicorn[standard]")
        sys.exit(1)

    app = jarvis.get_app()
    if app is None:
        print("API app not initialized")
        return

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="debug" if jarvis.debug else "info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_interactive(jarvis) -> None:
    """Run interactive chat mode in terminal."""
    print("\n" + "=" * 50)
    print("J.A.R.V.I.S. — Interactive Mode")
    print("Type 'exit' or 'quit' to stop")
    print("=" * 50 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("\nGoodbye, sir.")
                break

            result = await jarvis.process(user_input)
            if result.output:
                print(f"\nJARVIS: {result.output}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye, sir.")
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\nError: {e}\n")


async def main() -> None:
    args = parse_args()

    # Run setup wizard if requested
    if args.setup:
        from jarvis.core.setup_wizard import run_setup
        run_setup()
        return

    # Initialize JARVIS
    from jarvis.core.app import JARVIS

    jarvis = JARVIS(config_dir=args.data_dir, debug=args.debug)

    try:
        await jarvis.initialize()
    except Exception as e:
        print(f"Failed to initialize JARVIS: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # Run modes
    if args.no_api:
        await run_interactive(jarvis)
    elif not sys.stdin.isatty():
        # Non-interactive: run API server only
        await run_server(jarvis, args.host, args.port, args.no_ui)
    else:
        # Interactive: run both API and terminal
        server_task = asyncio.create_task(run_server(jarvis, args.host, args.port, args.no_ui))
        interactive_task = asyncio.create_task(run_interactive(jarvis))

        done, pending = await asyncio.wait(
            [server_task, interactive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

    await jarvis.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
