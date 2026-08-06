import httpx
from httpx import ASGITransport


class MockAPIClient:
    def __init__(self, app) -> None:
        self._transport = ASGITransport(app=app)
        self._client = httpx.AsyncClient(transport=self._transport, base_url="http://testserver")
        self._headers: dict[str, str] = {}
        self._cookies: dict[str, str] = {}

    async def get(self, url: str, **kwargs) -> dict:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        resp = await self._client.get(url, headers=headers, **kwargs)
        self._update_cookies(resp)
        return self._format_response(resp)

    async def post(self, url: str, data: dict = None, **kwargs) -> dict:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        resp = await self._client.post(url, json=data, headers=headers, **kwargs)
        self._update_cookies(resp)
        return self._format_response(resp)

    async def put(self, url: str, data: dict = None, **kwargs) -> dict:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        resp = await self._client.put(url, json=data, headers=headers, **kwargs)
        self._update_cookies(resp)
        return self._format_response(resp)

    async def delete(self, url: str, **kwargs) -> dict:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        resp = await self._client.delete(url, headers=headers, **kwargs)
        self._update_cookies(resp)
        return self._format_response(resp)

    def set_auth_token(self, token: str) -> None:
        self._headers["Authorization"] = f"Bearer {token}"

    def clear_auth(self) -> None:
        self._headers.pop("Authorization", None)

    def get_cookies(self) -> dict:
        return dict(self._cookies)

    def _update_cookies(self, resp: httpx.Response) -> None:
        for name, value in resp.cookies.items():
            self._cookies[name] = value

    def _format_response(self, resp: httpx.Response) -> dict:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": body,
        }

    async def close(self) -> None:
        await self._client.aclose()
