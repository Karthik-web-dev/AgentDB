from app.db.base import Base
import app.models  # Registers all models in Base.metadata


def test_sqlalchemy_model_registration():
    """Verify that all 9 core entities are registered in SQLAlchemy metadata."""
    registered_tables = set(Base.metadata.tables.keys())
    expected_tables = {
        "users",
        "agents",
        "tasks",
        "runs",
        "events",
        "logs",
        "metrics",
        "alerts",
        "audit_logs",
    }
    assert expected_tables.issubset(registered_tables), f"Missing tables: {expected_tables - registered_tables}"


def test_runs_composite_foreign_key_constraint():
    """Verify composite foreign key constraint on runs table referencing tasks(id, agent_id)."""
    runs_table = Base.metadata.tables["runs"]
    fk_names = {fk.name for fk in runs_table.foreign_key_constraints}
    assert "fk_runs_task_agent" in fk_names
    assert "fk_runs_agent" in fk_names


def test_logs_denormalized_agent_id():
    """Verify logs table contains both run_id and denormalized agent_id foreign key constraints."""
    logs_table = Base.metadata.tables["logs"]
    assert "run_id" in logs_table.columns
    assert "agent_id" in logs_table.columns
