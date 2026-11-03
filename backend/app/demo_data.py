"""Load a realistic demo dataset so the dashboard shows activity.

Everything is written through the same database rules the application uses, so the MySQL
triggers really run: failure-window alerts fire on the failed runs, threshold alerts fire on
the slow metrics, and the audit chain records the status changes.

Idempotent: if the demo account already exists, nothing is written.

    python -m app.demo_data
"""

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.alert import Alert
from app.models.event import Event
from app.models.log import Log
from app.models.metric import Metric
from app.models.run import Run
from app.models.task import Task
from app.models.user import User

DEMO_EMAIL = "demo@agentdb.dev"
DEMO_PASSWORD = "demo-password-123"
DEMO_NAME = "Demo Operator"

# (name, model, environment, typical latency ms, jitter ms)
AGENTS = [
    ("SupportBot", "gpt-4o", "production", 950, 260),
    ("CodeReviewer", "claude-3-5-sonnet", "production", 1800, 420),
    ("DocSummarizer", "gpt-4o-mini", "staging", 700, 160),
    ("DataPipeline", "gpt-4o", "development", 2400, 520),
]

# Prices per 1,000 tokens, effective from the start of 2026 (illustrative demo prices).
PRICING = [
    ("gpt-4o", 0.005, 0.015),
    ("gpt-4o-mini", 0.00015, 0.0006),
    ("claude-3-5-sonnet", 0.003, 0.015),
]

ERRORS = [
    "Rate limit exceeded for 1200 tokens",
    "Timeout after 30 seconds waiting for tool search_docs",
    "JSON schema validation failed on field 7",
    "Connection reset by peer",
]

TASK_TITLES = [
    "Summarize ticket backlog",
    "Review pull request",
    "Answer refund questions",
    "Draft weekly report",
    "Classify inbound email",
    "Extract invoice fields",
]


def _utc_now() -> datetime:
    """MySQL DATETIME is naive; store UTC without tzinfo."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def load_demo_data(db: Session) -> bool:
    """Write the demo dataset. Returns False (and writes nothing) if the demo account exists."""
    if db.execute(select(User.id).where(User.email == DEMO_EMAIL)).scalar_one_or_none() is not None:
        return False

    rnd = random.Random(20261021)
    now = _utc_now()

    user = User(
        email=DEMO_EMAIL,
        password_hash=get_password_hash(DEMO_PASSWORD),
        full_name=DEMO_NAME,
        role="developer",
    )
    db.add(user)
    db.flush()

    for model, price_in, price_out in PRICING:
        db.execute(
            text(
                "INSERT IGNORE INTO model_pricing (model, effective_from, input_usd_per_1k, output_usd_per_1k) "
                "VALUES (:m, '2026-01-01', :i, :o)"
            ),
            {"m": model, "i": price_in, "o": price_out},
        )

    agents = []
    for name, model, environment, _base, _jitter in AGENTS:
        agent = Agent(user_id=user.id, name=name, model=model, environment=environment, status="active", version="1.2.0",
                      description=f"{name} agent for demo purposes")
        db.add(agent)
        agents.append(agent)
    db.flush()
    # One agent is in maintenance so the status indicators show more than one state.
    agents[2].status = "maintenance"

    for agent in agents:
        for i, title in enumerate(rnd.sample(TASK_TITLES, 3)):
            status = ["completed", "in_progress", "pending"][i]
            db.add(Task(agent_id=agent.id, title=title, status=status, priority=["high", "medium", "low"][i]))
    db.flush()

    # Alert rules first, so that the runs and metrics below fire them through the database triggers.
    db.add_all(
        [
            Alert(user_id=user.id, agent_id=None, rule_name="Slow responses", rule_type="threshold",
                  metric_name="latency_ms", condition_operator=">", threshold_value=3000,
                  time_window_minutes=15, status="active"),
            Alert(user_id=user.id, agent_id=agents[1].id, rule_name="Failure burst", rule_type="failure_window",
                  metric_name="run_failures", condition_operator=">=", threshold_value=4,
                  time_window_minutes=60, status="active"),
            Alert(user_id=user.id, agent_id=agents[3].id, rule_name="Large prompts", rule_type="threshold",
                  metric_name="input_tokens", condition_operator=">", threshold_value=4000,
                  time_window_minutes=15, status="active"),
            Alert(user_id=user.id, agent_id=None, rule_name="Cost ceiling", rule_type="threshold",
                  metric_name="cost_usd", condition_operator=">", threshold_value=50,
                  time_window_minutes=1440, status="disabled"),
        ]
    )
    db.flush()

    # Runs over the last 36 hours, spread out with some jitter.
    per_agent_runs: dict[int, list[Run]] = {}
    for (name, model, environment, base, jitter), agent in zip(AGENTS, agents):
        runs = []
        for i in range(40):
            started = now - timedelta(minutes=i * 52 + rnd.randint(0, 40))
            latency = base + rnd.randint(-jitter, jitter)
            failed = rnd.random() < 0.06
            run = Run(
                agent_id=agent.id,
                status="failed" if failed else "completed",
                started_at=started,
                completed_at=started + timedelta(milliseconds=latency),
                execution_time_ms=latency,
                error_message=rnd.choice(ERRORS) if failed else None,
            )
            runs.append(run)
        per_agent_runs[agent.id] = runs
        db.add_all(runs)
    db.flush()

    # A burst of recent failures on CodeReviewer, so the failure-window rule fires.
    burst = [
        Run(agent_id=agents[1].id, status="failed", started_at=now - timedelta(minutes=m),
            completed_at=now - timedelta(minutes=m) + timedelta(seconds=40),
            execution_time_ms=40000, error_message=f"Rate limit exceeded for {400 + m} tokens")
        for m in (45, 33, 21, 12, 4)
    ]
    db.add_all(burst)
    per_agent_runs[agents[1].id].extend(burst)

    # Latency spikes on the two most recent SupportBot runs (they trigger "Slow responses").
    spikes = [r for r in per_agent_runs[agents[0].id] if r.status == "completed"][:2]
    for run in spikes:
        run.execution_time_ms = 6200 + rnd.randint(0, 900)
        run.completed_at = run.started_at + timedelta(milliseconds=run.execution_time_ms)

    # Runs in progress right now, so the dashboard shows live activity.
    live = [Run(agent_id=agent.id, status="running", started_at=now - timedelta(minutes=2 + k))
            for k, agent in enumerate(agents[:3])]
    db.add_all(live)
    db.flush()

    # Trace tree: DataPipeline coordinator with three sub-runs.
    coordinator_started = now - timedelta(minutes=25)
    coordinator = Run(agent_id=agents[3].id, status="completed", started_at=coordinator_started,
                      completed_at=coordinator_started + timedelta(milliseconds=6800), execution_time_ms=6800)
    db.add(coordinator)
    db.flush()
    for k in range(3):
        child_started = coordinator_started + timedelta(milliseconds=300 + k * 2100)
        db.add(Run(agent_id=agents[3].id, parent_run_id=coordinator.id, status="completed",
                   started_at=child_started, completed_at=child_started + timedelta(milliseconds=2100),
                   execution_time_ms=2100))
    db.flush()

    # Logs, metrics and events for every finished run.
    finished = [r for runs in per_agent_runs.values() for r in runs if r.status in ("completed", "failed")]
    for run in finished:
        ts = run.started_at + timedelta(milliseconds=rnd.randint(10, 400))
        if run.status == "failed":
            db.add(Log(run_id=run.id, agent_id=run.agent_id, severity="ERROR", message=run.error_message,
                       metadata_={"error_type": "provider_error"}, timestamp=ts))
            continue
        db.add(Log(run_id=run.id, agent_id=run.agent_id, severity="INFO",
                   message=f"Run completed in {run.execution_time_ms} ms", metadata_=None, timestamp=ts))
        if rnd.random() < 0.15:
            db.add(Log(run_id=run.id, agent_id=run.agent_id, severity="WARNING",
                       message="Retrying after transient failure", metadata_=None, timestamp=ts))
        db.add(Metric(run_id=run.id, metric_name="latency_ms", metric_value=float(run.execution_time_ms),
                      unit="ms", timestamp=run.completed_at))
        # DataPipeline sends large prompts, so its input-token rule fires sometimes.
        input_tokens = rnd.randint(2000, 5200) if run.agent_id == agents[3].id else rnd.randint(400, 2600)
        db.add(Metric(run_id=run.id, metric_name="input_tokens", metric_value=input_tokens,
                      unit="tokens", timestamp=run.completed_at))
        db.add(Metric(run_id=run.id, metric_name="output_tokens", metric_value=rnd.randint(120, 900),
                      unit="tokens", timestamp=run.completed_at))
        if rnd.random() < 0.3:
            db.add(Event(run_id=run.id, event_type="tool", event_name="search_docs",
                         payload={"query": "refund policy", "results": rnd.randint(1, 8)}, timestamp=ts))
    db.flush()

    # Status changes write audit rows through the audit trigger.
    support = agents[0]
    support.status = "maintenance"
    db.flush()
    support.status = "active"
    db.flush()

    # Make the rollups current for the whole demo window.
    db.execute(text("CALL sp_refresh_hourly_stats(:since)"), {"since": now - timedelta(days=7)})
    db.commit()
    return True


def main() -> None:
    db = SessionLocal()
    try:
        created = load_demo_data(db)
    finally:
        db.close()
    if created:
        print(f"Demo data loaded. Sign in with {DEMO_EMAIL} / {DEMO_PASSWORD}")
    else:
        print("Demo data already present; nothing to do.")


if __name__ == "__main__":
    main()
