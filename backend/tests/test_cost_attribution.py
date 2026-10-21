"""Novelty 6: token usage and cost attribution per run, with an explicit method."""

from datetime import datetime

import pytest
from sqlalchemy import text

from app.models.metric import Metric
from app.models.run import Run


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _price(db_session, model, effective, input_per_1k, output_per_1k):
    db_session.execute(
        text(
            "INSERT INTO model_pricing (model, effective_from, input_usd_per_1k, output_usd_per_1k) "
            "VALUES (:m, :e, :i, :o)"
        ),
        {"m": model, "e": effective, "i": input_per_1k, "o": output_per_1k},
    )
    db_session.commit()


def _run(db_session, agent_id, started, status="completed"):
    run = Run(agent_id=agent_id, status=status, started_at=started, completed_at=started, execution_time_ms=100)
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def _usage(db_session, run, input_tokens, output_tokens):
    db_session.add_all(
        [
            Metric(run_id=run.id, metric_name="input_tokens", metric_value=input_tokens, unit="tokens"),
            Metric(run_id=run.id, metric_name="output_tokens", metric_value=output_tokens, unit="tokens"),
        ]
    )
    db_session.commit()


def _breakdown(client, user, **params):
    response = client.get("/api/v1/analytics/runs-cost", headers=_auth(user), params=params)
    assert response.status_code == 200, response.text
    return {row["run_id"]: row for row in response.json()}


def test_priced_run_uses_per_thousand_token_rates(client, db_session, user_a, agent_a):
    _price(db_session, "gpt-4o", "2026-01-01", 0.005, 0.015)
    run = _run(db_session, agent_a["id"], datetime(2026, 3, 1, 12, 0, 0))
    _usage(db_session, run, 1000, 2000)

    row = _breakdown(client, user_a)[run.id]
    assert row["attribution_method"] == "direct"
    assert row["input_tokens"] == 1000 and row["output_tokens"] == 2000
    assert row["cost_usd"] == pytest.approx(0.035)  # 1 * 0.005 + 2 * 0.015


def test_run_without_usage_has_no_cost(client, db_session, user_a, agent_a):
    _price(db_session, "gpt-4o", "2026-01-01", 0.005, 0.015)
    run = _run(db_session, agent_a["id"], datetime(2026, 3, 1, 12, 0, 0))
    row = _breakdown(client, user_a)[run.id]
    assert row["attribution_method"] == "no_usage"
    assert row["cost_usd"] is None


def test_run_of_unpriced_model_is_reported_as_unpriced(client, db_session, user_a):
    agent = client.post("/api/v1/agents", headers=_auth(user_a), json={"name": "Mystery", "model": "unknown-model"}).json()
    run = _run(db_session, agent["id"], datetime(2026, 3, 1, 12, 0, 0))
    _usage(db_session, run, 500, 500)
    row = _breakdown(client, user_a)[run.id]
    assert row["attribution_method"] == "unpriced"
    assert row["cost_usd"] is None


def test_price_history_applies_the_price_in_force_when_the_run_started(client, db_session, user_a, agent_a):
    _price(db_session, "gpt-4o", "2026-01-01", 0.01, 0.01)
    _price(db_session, "gpt-4o", "2026-06-01", 0.10, 0.10)
    early = _run(db_session, agent_a["id"], datetime(2026, 3, 1, 12, 0, 0))
    late = _run(db_session, agent_a["id"], datetime(2026, 7, 1, 12, 0, 0))
    _usage(db_session, early, 1000, 1000)
    _usage(db_session, late, 1000, 1000)

    rows = _breakdown(client, user_a)
    assert rows[early.id]["cost_usd"] == pytest.approx(0.02)
    assert rows[late.id]["cost_usd"] == pytest.approx(0.20)


def test_usage_rows_are_summed_per_run(client, db_session, user_a, agent_a):
    _price(db_session, "gpt-4o", "2026-01-01", 0.005, 0.015)
    run = _run(db_session, agent_a["id"], datetime(2026, 3, 1, 12, 0, 0))
    _usage(db_session, run, 400, 100)
    _usage(db_session, run, 600, 900)
    row = _breakdown(client, user_a)[run.id]
    assert row["input_tokens"] == 1000
    assert row["output_tokens"] == 1000


@pytest.mark.parametrize("bad_value", [-5, 2.5])
def test_token_metrics_must_be_whole_non_negative_numbers(db_session, agent_a, bad_value):
    run = _run(db_session, agent_a["id"], datetime(2026, 3, 1, 12, 0, 0))
    with pytest.raises(Exception, match="non-negative whole numbers"):
        db_session.add(Metric(run_id=run.id, metric_name="input_tokens", metric_value=bad_value, unit="tokens"))
        db_session.commit()
    db_session.rollback()


def test_non_token_metrics_are_not_restricted(db_session, agent_a):
    run = _run(db_session, agent_a["id"], datetime(2026, 3, 1, 12, 0, 0))
    db_session.add(Metric(run_id=run.id, metric_name="temperature", metric_value=-3.5, unit="C"))
    db_session.commit()


def test_agent_cost_report_totals_priced_runs(client, db_session, user_a, agent_a):
    _price(db_session, "gpt-4o", "2026-01-01", 0.01, 0.02)
    priced = _run(db_session, agent_a["id"], datetime(2026, 3, 1, 12, 0, 0))
    _usage(db_session, priced, 1000, 1000)
    _run(db_session, agent_a["id"], datetime(2026, 3, 2, 12, 0, 0))

    response = client.get("/api/v1/analytics/cost", headers=_auth(user_a))
    assert response.status_code == 200
    (row,) = response.json()
    assert row["agent_id"] == agent_a["id"]
    assert row["total_runs"] == 2
    assert row["priced_runs"] == 1
    assert row["runs_without_usage"] == 1
    assert row["total_cost_usd"] == pytest.approx(0.03)


def test_cost_report_respects_the_time_range(client, db_session, user_a, agent_a):
    _price(db_session, "gpt-4o", "2026-01-01", 0.01, 0.02)
    run = _run(db_session, agent_a["id"], datetime(2026, 3, 1, 12, 0, 0))
    _usage(db_session, run, 1000, 1000)
    response = client.get(
        "/api/v1/analytics/cost",
        headers=_auth(user_a),
        params={"since": "2026-04-01T00:00:00", "until": "2026-05-01T00:00:00"},
    )
    assert response.json() == []


def test_cost_is_invisible_to_other_users(client, db_session, user_a, user_b, agent_a):
    _price(db_session, "gpt-4o", "2026-01-01", 0.01, 0.02)
    run = _run(db_session, agent_a["id"], datetime(2026, 3, 1, 12, 0, 0))
    _usage(db_session, run, 1000, 1000)
    assert client.get("/api/v1/analytics/cost", headers=_auth(user_b)).json() == []
    assert _breakdown(client, user_b) == {}


def test_run_cost_for_unowned_agent_is_not_found(client, user_a, user_b, agent_a):
    response = client.get("/api/v1/analytics/runs-cost", headers=_auth(user_b), params={"agent_id": agent_a["id"]})
    assert response.status_code == 404
