"""
Symmetric encryption for sensitive credentials stored in the Vello database
(currently the user's Kortex personal API token).

Key is derived from SECRET_KEY so rotating SECRET_KEY invalidates all stored
tokens (intentional — users would need to re-connect Kortex after a rotation).
"""
import base64
import hashlib
import os
from functools import lru_cache

from cryptography.fernet import Fernet


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    secret = os.environ.get("SECRET_KEY", "insecure-dev-key-change-in-production")
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        # Token was stored under a different SECRET_KEY (rotation) or is
        # malformed. Treat as missing — caller will prompt for reconnection.
        return ""
