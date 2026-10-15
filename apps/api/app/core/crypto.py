"""Encryption for sensitive memories, using a key separate from the database's own.

Fernet (AES-128-CBC with HMAC) from the ``cryptography`` package. In production
the key comes from the secrets manager; rotating it needs a re-encryption job.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"mentor-dev-only-key").digest())


@lru_cache
def _fernet() -> Fernet:
    configured = get_settings().sensitive_data_key
    return Fernet(configured.get_secret_value().encode() if configured else _DEV_KEY)


def reset_crypto() -> None:
    _fernet.cache_clear()


def encrypt(text: str) -> bytes:
    return _fernet().encrypt(text.encode())


def decrypt(token: bytes) -> str:
    try:
        return _fernet().decrypt(token).decode()
    except InvalidToken as exc:
        raise ValueError("Could not decrypt value; the key may have changed") from exc
