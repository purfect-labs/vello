"""Critical security paths."""
import pytest


def test_validate_config_rejects_default_secret_in_production(monkeypatch):
    monkeypatch.setattr("vello.config.SECRET_KEY", "change-me-in-production")
    monkeypatch.setattr("vello.config.ENV", "production")
    from vello.config import validate_config
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_config()


def test_validate_config_rejects_short_secret_in_production(monkeypatch):
    monkeypatch.setattr("vello.config.SECRET_KEY", "short")
    monkeypatch.setattr("vello.config.ENV", "production")
    from vello.config import validate_config
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_config()


def test_validate_config_allows_dev_default():
    """Dev environments shouldn't be blocked by SECRET_KEY validation."""
    from vello.config import validate_config
    # ENV=test in conftest; should not raise
    validate_config()


# ── Token encryption ──────────────────────────────────────────────────────────

def test_kortex_token_round_trip(registered_user_id):
    from vello.database import set_kortex_token, get_kortex_token
    set_kortex_token(registered_user_id, "ktx_abc123secrettoken")
    assert get_kortex_token(registered_user_id) == "ktx_abc123secrettoken"


def test_kortex_token_stored_encrypted(registered_user_id):
    """The stored value should NOT be the plaintext token."""
    from vello.database import set_kortex_token, get_connection
    set_kortex_token(registered_user_id, "ktx_plaintext_marker")
    conn = get_connection()
    row = conn.execute("SELECT kortex_token FROM users WHERE id=?", (registered_user_id,)).fetchone()
    conn.close()
    assert "ktx_plaintext_marker" not in row["kortex_token"]
    assert row["kortex_token"]  # but something is stored


def test_kortex_token_clear(registered_user_id):
    from vello.database import set_kortex_token, get_kortex_token
    set_kortex_token(registered_user_id, "ktx_something")
    set_kortex_token(registered_user_id, "")
    assert get_kortex_token(registered_user_id) == ""


def test_decrypt_handles_garbage():
    """A malformed ciphertext shouldn't crash; should return ''."""
    from vello.crypto import decrypt
    assert decrypt("not-actual-fernet-output") == ""
