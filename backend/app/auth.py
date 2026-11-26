"""Firebase refresh-token -> ID-token exchange with an in-memory cache."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

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
        on_rotate: Callable[[str], None] | None = None,
    ) -> None:
        self._on_rotate = on_rotate
        self._refresh_token = refresh_token
        self._api_key = api_key
        self._client = client
        self._clock = clock
        self._id_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self._refresh_token and self._api_key)

    def set_credentials(self, refresh_token: str, api_key: str) -> None:
        self._refresh_token = refresh_token
        self._api_key = api_key
        self.invalidate()

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
                "Boostcamp is not connected. Add your credentials in Settings "
                "(or set BOOSTCAMP_REFRESH_TOKEN and FIREBASE_API_KEY in .env)."
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
                    "fresh refresh token from DevTools into Settings (see README)."
                )
            raise BoostcampAuthError(f"Token refresh failed: HTTP {resp.status_code} {code or resp.text[:200]}")

        body = resp.json()
        self._id_token = body["id_token"]
        self._expires_at = self._clock() + int(body.get("expires_in", 3600))
        # Google may rotate the refresh token; keep the newest (and persist it if asked).
        new = body.get("refresh_token")
        if new and new != self._refresh_token:
            self._refresh_token = new
            if self._on_rotate:
                self._on_rotate(new)


def _error_code(resp: httpx.Response) -> str | None:
    try:
        err = resp.json().get("error")
    except ValueError:
        return None
    if isinstance(err, dict):
        return err.get("message")
    return err if isinstance(err, str) else None


async def verify_credentials(refresh_token: str, api_key: str) -> str:
    """Exchange once to prove the credentials work. Returns the (possibly rotated) refresh token."""
    tm = TokenManager(refresh_token, api_key)
    await tm.get_id_token()
    return tm._refresh_token
