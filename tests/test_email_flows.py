"""Email verification + password reset flows."""
import pytest


# ── Email verification ────────────────────────────────────────────────────────

def test_set_and_verify_email_token(registered_user_id):
    from vello.database import set_verification_token, verify_email_token, get_user_by_id

    set_verification_token(registered_user_id, "tok-abc-123")
    user = get_user_by_id(registered_user_id)
    assert user["verification_token"] == "tok-abc-123"
    assert user["email_verified"] == 0

    verified = verify_email_token("tok-abc-123")
    assert verified is not None
    assert verified["email_verified"] == 1
    assert verified["verification_token"] is None  # cleared on success


def test_verify_unknown_token_returns_none():
    from vello.database import verify_email_token
    assert verify_email_token("never-issued") is None


def test_verify_expired_token_returns_none(registered_user_id):
    from vello.database import set_verification_token, verify_email_token, get_connection
    set_verification_token(registered_user_id, "stale-tok")
    # Backdate the sent_at to 25h ago
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE users SET verification_sent_at=datetime('now', '-25 hours') WHERE id=?",
            (registered_user_id,),
        )
    conn.close()
    assert verify_email_token("stale-tok") is None


# ── Password reset ────────────────────────────────────────────────────────────

def test_create_and_consume_reset_token(registered_user_id):
    from vello.database import create_password_reset_token, get_valid_reset_token, consume_reset_token
    token = create_password_reset_token(registered_user_id)
    row = get_valid_reset_token(token)
    assert row is not None
    assert row["user_id"] == registered_user_id

    consume_reset_token(token)
    assert get_valid_reset_token(token) is None  # used=1 now


def test_reset_token_expires(registered_user_id):
    from vello.database import create_password_reset_token, get_valid_reset_token, get_connection
    token = create_password_reset_token(registered_user_id)
    # Backdate expiry to the past
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE password_reset_tokens SET expires_at=datetime('now', '-1 hour') WHERE token=?",
            (token,),
        )
    conn.close()
    assert get_valid_reset_token(token) is None


def test_change_password_updates_hash(registered_user_id):
    from vello.database import change_password, get_user_by_id, verify_password
    original = get_user_by_id(registered_user_id)
    change_password(registered_user_id, "brand-new-password-99")
    refreshed = get_user_by_id(registered_user_id)
    assert refreshed["password_hash"] != original["password_hash"]
    assert verify_password(refreshed, "brand-new-password-99") is True
    assert verify_password(refreshed, "secure-test-password-42") is False


# ── Email sender — graceful behavior on missing AWS creds + on send error ────

def test_send_verification_silent_without_aws_creds(monkeypatch):
    """Missing IAM creds shouldn't crash the registration flow — just log+return."""
    from botocore.exceptions import NoCredentialsError

    class _FakeSES:
        def send_email(self, **_):
            raise NoCredentialsError()

    monkeypatch.setattr("vello.email.boto3.client", lambda *a, **kw: _FakeSES())
    from vello.email import send_verification_email
    assert send_verification_email("user@example.com", "tok123") is False


def test_send_reset_silent_without_aws_creds(monkeypatch):
    from botocore.exceptions import NoCredentialsError

    class _FakeSES:
        def send_email(self, **_):
            raise NoCredentialsError()

    monkeypatch.setattr("vello.email.boto3.client", lambda *a, **kw: _FakeSES())
    from vello.email import send_password_reset_email
    assert send_password_reset_email("user@example.com", "tok123") is False


def test_send_verification_returns_true_on_success(monkeypatch):
    """Happy path: boto3 returns successfully → True."""
    sent: dict = {}

    class _FakeSES:
        def send_email(self, **kwargs):
            sent.update(kwargs)
            return {"MessageId": "abc-123"}

    monkeypatch.setattr("vello.email.boto3.client", lambda *a, **kw: _FakeSES())
    from vello.email import send_verification_email
    assert send_verification_email("user@example.com", "tok123") is True
    assert sent["Destination"]["ToAddresses"] == ["user@example.com"]
    assert "Verify" in sent["Message"]["Subject"]["Data"]
    assert "tok123" in sent["Message"]["Body"]["Html"]["Data"]
