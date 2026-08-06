from unittest.mock import AsyncMock
from collections.abc import AsyncGenerator


class MockAIService:
    def __init__(self) -> None:
        self._default_response = {
            "content": "Mock response",
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "role": "assistant",
        }
        self._response = self._default_response["content"]
        self._error: str | None = None
        self._call_history: list[dict] = []
        self._embedding = [0.1] * 1536

    async def chat(self, messages: list[dict], model: str = "gpt-4o") -> dict:
        self._call_history.append({"method": "chat", "messages": messages, "model": model})
        if self._error:
            error = self._error
            self._error = None
            raise Exception(error)
        return {
            "content": self._response,
            "model": model,
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "role": "assistant",
        }

    async def embed(self, text: str) -> list[float]:
        self._call_history.append({"method": "embed", "text": text})
        if self._error:
            error = self._error
            self._error = None
            raise Exception(error)
        return list(self._embedding)

    async def complete(self, prompt: str) -> str:
        self._call_history.append({"method": "complete", "prompt": prompt})
        if self._error:
            error = self._error
            self._error = None
            raise Exception(error)
        return self._response

    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        self._call_history.append({"method": "stream_chat", "messages": messages})
        if self._error:
            error = self._error
            self._error = None
            raise Exception(error)
        for token in self._response.split():
            yield token + " "

    def set_response(self, response: str) -> None:
        self._response = response

    def set_error(self, error: str) -> None:
        self._error = error

    def get_call_history(self) -> list[dict]:
        return list(self._call_history)

    def reset(self) -> None:
        self._call_history.clear()
        self._response = self._default_response["content"]
        self._error = None
