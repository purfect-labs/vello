"""Shared fixtures for Vello tests."""
import os

import pytest

# Force test config before any vello imports run
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-chars-long")
os.environ.setdefault("DB_PATH", "/tmp/vello-test.db")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")


@pytest.fixture(autouse=True)
def clean_db():
    """Reset the test DB before each test for full isolation."""
    db_path = os.environ.get("DB_PATH", "/tmp/vello-test.db")
    for path in (db_path, db_path + "-wal", db_path + "-shm"):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    from vello.database import init_db
    init_db()
    yield

    for path in (db_path, db_path + "-wal", db_path + "-shm"):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


@pytest.fixture
def registered_user_id() -> str:
    from vello.database import create_user
    return create_user("test@example.com", "secure-test-password-42")
