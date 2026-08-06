"""Quick test for Gemini integration."""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, r"C:\Users\HOME\Desktop\JARVIS")

from jarvis.config.settings import get_settings


async def test_gemini():
    """Test Gemini streaming."""
    settings = get_settings()

    print(f"Provider: {settings.ai.provider}")
    print(f"Model: {settings.ai.model}")
    print(f"API Key set: {bool(settings.ai.api_key)}")

    if not settings.ai.api_key:
        print("\nNo API key found. Set GEMINI_API_KEY environment variable.")
        print("Get a free key at: https://aistudio.google.com/apikey")
        return

    from jarvis.core.brain.streaming import StreamingGenerator

    generator = StreamingGenerator(settings.ai)

    messages = [
        {"role": "system", "content": "You are JARVIS, a helpful AI assistant."},
        {"role": "user", "content": "Hello! What can you do?"},
    ]

    print("\nStreaming response:")
    print("-" * 50)

    async for chunk in generator.stream(messages):
        if chunk.delta:
            print(chunk.delta, end="", flush=True)
        if chunk.finish_reason:
            print(f"\n\nFinish reason: {chunk.finish_reason}")
            break

    print("\n" + "=" * 50)
    print("Test complete!")


if __name__ == "__main__":
    asyncio.run(test_gemini())
