"""Firebase refresh-token -> ID-token exchange with an in-memory cache."""

from __future__ import annotations

import asyncio
import time

import httpx

TOKEN_URL = "https://securetoken.googleapis.com/v1/token"
REFRESH_MARGIN_S = 5 * 60


class BoostcampAuthError(RuntimeError):
    """Raised when the refresh token cannot be exchanged for an ID token."""


class TokenManager:
    def __init__(
        self,
        refresh_token: str,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        clock=time.monotonic,
    ) -> None:
        self._refresh_token = refresh_token
        self._api_key = api_key
        self._client = client
        self._clock = clock
        self._id_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        self._id_token = None
        self._expires_at = 0.0

    async def get_id_token(self) -> str:
        async with self._lock:
            if self._id_token and self._clock() < self._expires_at - REFRESH_MARGIN_S:
                return self._id_token
            await self._refresh()
            assert self._id_token
            return self._id_token

    async def _refresh(self) -> None:
        if not self._refresh_token or not self._api_key:
            raise BoostcampAuthError(
                "BOOSTCAMP_REFRESH_TOKEN and FIREBASE_API_KEY must be set in .env"
            )
        client = self._client or httpx.AsyncClient(timeout=20)
        try:
            resp = await client.post(
                TOKEN_URL,
                params={"key": self._api_key},
                data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            )
        except httpx.HTTPError as exc:
            raise BoostcampAuthError(f"Token refresh request failed: {exc}") from exc
        finally:
            if self._client is None:
                await client.aclose()

        if resp.status_code != 200:
            code = _error_code(resp)
            if code in {"TOKEN_EXPIRED", "INVALID_REFRESH_TOKEN", "USER_DISABLED", "USER_NOT_FOUND"}:
                raise BoostcampAuthError(
                    f"Refresh token rejected ({code}). Log in to www.boostcamp.app and copy a "
                    "fresh refresh token from DevTools into .env (see README)."
                )
            raise BoostcampAuthError(f"Token refresh failed: HTTP {resp.status_code} {code or resp.text[:200]}")

        body = resp.json()
        self._id_token = body["id_token"]
        self._expires_at = self._clock() + int(body.get("expires_in", 3600))
        # Google may rotate the refresh token; keep the newest in memory.
        if body.get("refresh_token"):
            self._refresh_token = body["refresh_token"]


def _error_code(resp: httpx.Response) -> str | None:
    try:
        err = resp.json().get("error")
    except ValueError:
        return None
    if isinstance(err, dict):
        return err.get("message")
    return err if isinstance(err, str) else None
