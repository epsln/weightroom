"""Encryption at rest for secrets stored in SQLite (Boostcamp credentials).

The key comes from WEIGHTROOM_SECRET when set. Otherwise a random key is generated
once and kept in `secret.key` next to the database (mode 0600). Keeping the key
outside the DB means a leaked/backed-up `weightroom.db` alone does not expose the
Boostcamp refresh token; set WEIGHTROOM_SECRET to keep the key out of the data dir too.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import Settings

log = logging.getLogger("weightroom.crypto")


class SecretError(RuntimeError):
    """Raised when stored secrets cannot be decrypted (key changed or data corrupt)."""


def _derive(secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def _load_or_create_key_file(path: Path) -> bytes:
    if path.is_file():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    log.info("Generated encryption key at %s (set WEIGHTROOM_SECRET to manage it yourself)", path)
    return key


def load_cipher(settings: Settings) -> "Cipher":
    if settings.secret:
        return Cipher(Fernet(_derive(settings.secret)))
    path = settings.secret_key_path
    key = _load_or_create_key_file(Path(path)) if path else Fernet.generate_key()
    return Cipher(Fernet(key))


class Cipher:
    def __init__(self, fernet: Fernet) -> None:
        self._f = fernet

    def encrypt(self, plaintext: str) -> str:
        return self._f.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._f.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise SecretError(
                "Stored Boostcamp credentials cannot be decrypted (encryption key changed?). "
                "Re-enter them in Settings."
            ) from exc
