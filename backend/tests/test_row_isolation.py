"""Novelty 11: database-enforced row isolation through owned views and the session variable."""

import pytest
from sqlalchemy import text

from app.db.session import engine


def _create_run(client, user, agent_id):
    response = client.post(
        "/api/v1/runs",
        headers={"Authorization": user["Authorization"]},
        json={"agent_id": agent_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _visible_run_ids(conn, user_id=None):
    if user_id is None:
        conn.execute(text("SET @app_user_id = NULL"))
    else:
        conn.execute(text("SET @app_user_id = :uid"), {"uid": user_id})
    return sorted(r[0] for r in conn.execute(text("SELECT id FROM v_owned_runs")).all())


def test_owned_view_is_empty_when_no_user_is_set(client, user_a, agent_a):
    _create_run(client, user_a, agent_a["id"])
    with engine.connect() as conn:
        assert _visible_run_ids(conn, None) == []


def test_owned_view_shows_only_the_users_own_runs_even_without_a_where_clause(client, user_a, user_b, agent_a):
    bob_agent = client.post(
        "/api/v1/agents", headers={"Authorization": user_b["Authorization"]}, json={"name": "Bob", "model": "m"}
    ).json()
    alice_runs = [_create_run(client, user_a, agent_a["id"])["id"] for _ in range(2)]
    bob_runs = [_create_run(client, user_b, bob_agent["id"])["id"]]

    with engine.connect() as conn:
        assert _visible_run_ids(conn, user_a["user_id"]) == sorted(alice_runs)
        assert _visible_run_ids(conn, user_b["user_id"]) == sorted(bob_runs)


def test_owned_views_for_agents_alerts_and_signatures_follow_the_same_rule(client, user_a, user_b, agent_a):
    client.post("/api/v1/alerts", headers={"Authorization": user_a["Authorization"]},
                json={"rule_name": "r", "metric_name": "latency_ms", "condition_operator": ">", "threshold_value": 1})
    with engine.connect() as conn:
        conn.execute(text("SET @app_user_id = :uid"), {"uid": user_b["user_id"]})
        assert conn.execute(text("SELECT COUNT(*) FROM v_owned_agents")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM v_owned_alerts")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM v_owned_error_signatures")).scalar() == 0

        conn.execute(text("SET @app_user_id = :uid"), {"uid": user_a["user_id"]})
        assert conn.execute(text("SELECT COUNT(*) FROM v_owned_agents")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM v_owned_alerts")).scalar() == 1


@pytest.mark.parametrize("path", ["/api/v1/runs", "/api/v1/agents", "/api/v1/alerts"])
def test_api_rejects_requests_without_a_token(client, path):
    """Authentication is still required; the views are a second line of defence, not the first."""
    assert client.get(path).status_code == 401


def test_identity_does_not_leak_to_the_next_session_on_a_pooled_connection():
    """Regression: a connection returned to the pool must not carry the previous user's identity."""
    from app.db.session import SessionLocal, set_app_user

    first = SessionLocal()
    set_app_user(first, 4242)
    assert first.execute(text("SELECT fn_current_user_id()")).scalar() == 4242
    first.commit()
    first.close()

    second = SessionLocal()
    try:
        assert second.execute(text("SELECT fn_current_user_id()")).scalar() is None
    finally:
        second.close()


def test_identity_survives_a_commit_within_the_same_session():
    """Regression: a commit may move the session to another connection; the identity must follow it."""
    from app.db.session import SessionLocal, set_app_user

    session = SessionLocal()
    try:
        set_app_user(session, 777)
        session.execute(text("SELECT 1"))
        session.commit()
        assert session.execute(text("SELECT fn_current_user_id()")).scalar() == 777
    finally:
        session.close()
