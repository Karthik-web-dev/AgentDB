"""Shared pytest fixtures for AgentDB.

All tests run against a real MySQL 8 server. The schema is built from the same
SQL files the project ships (database/*.sql + database/migrations/*.sql), so tables,
views, procedures, triggers and events are tested exactly as they run in production.

Required configuration (backend/.env or environment variables):
    TEST_DATABASE_URL=mysql+pymysql://user:password@host:port/agentdb_test

The database name must end in `_test`. It is dropped and rebuilt at the start of
every test session, so never point it at real data.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.exit(
        "TEST_DATABASE_URL is not set. Add it to backend/.env, for example:\n"
        "TEST_DATABASE_URL=mysql+pymysql://root:<password>@127.0.0.1:3306/agentdb_test",
        returncode=2,
    )

_test_url = make_url(TEST_DATABASE_URL)
if not (_test_url.database or "").endswith("_test"):
    pytest.exit("TEST_DATABASE_URL must point at a database whose name ends in _test.", returncode=2)

TEST_DB_NAME = _test_url.database

# The application reads these at import time, so set them before any app module is imported.
# Environment variables take precedence over backend/.env.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DEBUG"] = "False"  # keeps SQL echo off in test output
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-with-more-than-32-characters")

from app.db.bootstrap import build_database  # noqa: E402
from app.db.session import engine  # noqa: E402

# Singleton bookkeeping rows that must survive a table clean-up.
# Each entry is restored to its initial state after TRUNCATE.
_SINGLETON_RESETS = {
    "audit_chain_head": "UPDATE audit_chain_head SET last_seq = 0, last_hash = REPEAT('0', 64) WHERE id = 1",
}


@pytest.fixture(scope="session", autouse=True)
def database_schema():
    """Build the test database once per session from database/*.sql."""
    build_database(TEST_DATABASE_URL, include_seed=False, reset=True)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(database_schema):
    """Empty every table before each test, then restore singleton rows.

    TRUNCATE is used on purpose: it bypasses row-level triggers, so append-only
    protection on logs, events and audit_logs cannot block test clean-up.
    """
    with engine.begin() as conn:
        all_tables = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_type = 'BASE TABLE'"
            ),
            {"schema": TEST_DB_NAME},
        ).scalars().all()
        # Singleton tables are reset in place, never truncated: truncating would delete the
        # only row and nothing would put it back.
        tables = [t for t in all_tables if t not in _SINGLETON_RESETS]
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in tables:
            conn.execute(text(f"TRUNCATE TABLE `{table}`"))
        for reset_sql in _SINGLETON_RESETS.values():
            conn.execute(text(reset_sql))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    yield




@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session():
    """A plain SQLAlchemy session for tests that insert rows directly (logs, metrics, runs, ...)."""
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _register_and_login(client, email: str, full_name: str = "Test User") -> dict:
    password = "correct-horse-battery"
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register.status_code == 201, register.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}", "user_id": register.json()["id"]}


@pytest.fixture()
def user_a(client):
    """First registered user: {'Authorization': ..., 'user_id': ...}."""
    return _register_and_login(client, "alice@example.com", "Alice Example")


@pytest.fixture()
def user_b(client):
    """Second user, used to prove that ownership checks isolate data."""
    return _register_and_login(client, "bob@example.com", "Bob Example")


@pytest.fixture()
def agent_a(client, user_a):
    response = client.post(
        "/api/v1/agents",
        headers={"Authorization": user_a["Authorization"]},
        json={"name": "SupportBot", "model": "gpt-4o", "environment": "production"},
    )
    assert response.status_code == 201, response.text
    return response.json()
