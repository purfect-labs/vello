"""
Hardened client for talking to Kortex.

Verifies Ed25519 signatures on signed responses (new in Kortex's audit pass)
so we know imported data wasn't tampered with in transit. Caches Kortex's
public key in-process — re-fetches on signature mismatch (key rotation).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import threading
from typing import Optional

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from vello.config import KORTEX_API_URL, KORTEX_PUBLIC_KEY_URL

log = logging.getLogger(__name__)

_pubkey_lock = threading.Lock()
_pubkey_cache: tuple[Ed25519PublicKey, str] | None = None  # (key, fingerprint)


class KortexAuthError(Exception):
    """User's Kortex token was rejected — caller should clear the stored token."""


class KortexUnreachable(Exception):
    """Network-level failure talking to Kortex — caller can retry."""


class KortexSignatureError(Exception):
    """Response signature didn't verify even after a key refetch — possible MITM or tamper."""


# ── Public key cache ──────────────────────────────────────────────────────────

def _fetch_public_key() -> Ed25519PublicKey:
    """Fetch and parse Kortex's Ed25519 public key. Cached in-process."""
    global _pubkey_cache
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(KORTEX_PUBLIC_KEY_URL)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        raise KortexUnreachable(f"could not fetch Kortex public key: {exc}") from exc

    pem = data.get("public_key", "")
    fingerprint = data.get("fingerprint", "")
    if not pem:
        raise KortexUnreachable("Kortex public-key response missing 'public_key'")
    pub = serialization.load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(pub, Ed25519PublicKey):
        raise KortexUnreachable("Kortex public key is not Ed25519")
    with _pubkey_lock:
        _pubkey_cache = (pub, fingerprint)
    return pub


def _get_public_key(force_refresh: bool = False) -> Ed25519PublicKey:
    if force_refresh:
        return _fetch_public_key()
    with _pubkey_lock:
        cached = _pubkey_cache
    if cached:
        return cached[0]
    return _fetch_public_key()


# ── Signature verification ────────────────────────────────────────────────────

def _verify_signature(body: bytes, signed_at: str, signature_b64: str) -> bool:
    """Returns True iff the signature is valid for (signed_at, sha256(body))."""
    body_hash = hashlib.sha256(body).hexdigest()
    msg = f"{signed_at}:{body_hash}".encode("utf-8")
    try:
        sig = base64.b64decode(signature_b64)
    except Exception:
        return False

    pub = _get_public_key()
    try:
        pub.verify(sig, msg)
        return True
    except Exception:
        # Try once more with a freshly-fetched key in case of key rotation.
        try:
            pub = _get_public_key(force_refresh=True)
            pub.verify(sig, msg)
            return True
        except Exception:
            return False


# ── High-level calls ──────────────────────────────────────────────────────────

def validate_token(token: str) -> bool:
    """Cheap call to /user/token; returns True iff Kortex accepts the token."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{KORTEX_API_URL}/user/token",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as exc:
        raise KortexUnreachable(str(exc)) from exc
    if resp.status_code == 401:
        return False
    if resp.status_code != 200:
        raise KortexUnreachable(f"unexpected status {resp.status_code}")
    return True


def fetch_export(token: str) -> dict:
    """
    Pull /vello/export, verify the Ed25519 signature, return the parsed body.

    Raises:
      KortexAuthError       — token rejected (401); caller should clear it.
      KortexUnreachable     — network/server error.
      KortexSignatureError  — signature mismatch even after a pubkey refresh.
    """
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{KORTEX_API_URL}/vello/export",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as exc:
        raise KortexUnreachable(str(exc)) from exc

    if resp.status_code == 401:
        raise KortexAuthError("kortex token rejected")
    if resp.status_code != 200:
        raise KortexUnreachable(f"unexpected status {resp.status_code}")

    sig = resp.headers.get("X-Kortex-Signature")
    signed_at = resp.headers.get("X-Kortex-Signed-At")
    if sig and signed_at:
        if not _verify_signature(resp.content, signed_at, sig):
            raise KortexSignatureError("response signature did not verify")
    else:
        # Older Kortex without signing — log but accept. Once Kortex's signed
        # release is rolled out everywhere this branch should become an error.
        log.warning("Kortex response was unsigned; proceeding without verification")

    return resp.json()
