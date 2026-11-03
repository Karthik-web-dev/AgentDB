"""Build an AgentDB MySQL database from the project's SQL files.

The SQL files in database/ are the single source of truth for the schema. This module
applies them in a fixed order so that the tests and a fresh developer database are
built exactly the same way:

    1. database/schema.sql, indexes.sql, views.sql, procedures.sql, triggers.sql
    2. database/migrations/*.sql   (one file per novelty, applied in name order)
    3. database/seed.sql           (optional development data, loaded last)

Usage (creates a new database; --reset drops an existing one first):
    python -m app.db.bootstrap --url mysql+pymysql://user:pass@host:3306/agentdb --seed
    python -m app.db.bootstrap --url mysql+pymysql://user:pass@host:3306/agentdb --seed --reset
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from app.core.config import settings

DATABASE_DIR = Path(__file__).resolve().parents[3] / "database"

BASE_FILES = ["schema.sql", "indexes.sql", "views.sql", "procedures.sql", "triggers.sql"]
SEED_FILE = "seed.sql"


def split_sql(script: str) -> list[str]:
    """Split a .sql script into individual statements, honouring DELIMITER changes.

    Full-line comments are dropped first, so a comment ending in ';' cannot end a statement.
    USE and CREATE DATABASE statements are dropped: the target database is chosen by the caller.
    """
    statements: list[str] = []
    delimiter = ";"
    buffer: list[str] = []
    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not buffer and (not line or line.startswith("--")):
            continue
        if line.upper().startswith("DELIMITER "):
            delimiter = line.split(None, 1)[1].strip()
            continue
        buffer.append(raw_line)
        joined = "\n".join(buffer).rstrip()
        if joined.endswith(delimiter):
            body = joined[: -len(delimiter)].strip()
            if body:
                statements.append(body)
            buffer = []
    leftover = "\n".join(buffer).strip()
    if leftover:
        statements.append(leftover)
    return [s for s in statements if not s.upper().startswith(("USE ", "CREATE DATABASE"))]


def ordered_files(include_seed: bool) -> list[Path]:
    """Return the SQL files in the order they must be applied."""
    files = [DATABASE_DIR / name for name in BASE_FILES]
    files += sorted((DATABASE_DIR / "migrations").glob("*.sql"))
    if include_seed:
        files.append(DATABASE_DIR / SEED_FILE)
    return files


def _server_url(url: URL) -> URL:
    """Same host and credentials as `url`, but without a database selected."""
    return URL.create(
        url.drivername,
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        query=url.query,
    )


def schema_is_built(database_url: str) -> bool:
    """True if the AgentDB schema is already present (the `users` table exists in the database)."""
    url = make_url(database_url)
    server_engine = create_engine(url)
    try:
        with server_engine.connect() as conn:
            return bool(
                conn.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = :name AND table_name = 'users'"
                    ),
                    {"name": url.database},
                ).scalar()
            )
    except Exception:
        # Database or server not reachable yet: treat the schema as not built.
        return False
    finally:
        server_engine.dispose()


def build_database(database_url: str, include_seed: bool = False, reset: bool = False) -> None:
    """Create the database named in `database_url` and load every project SQL file into it.

    Raises RuntimeError if the database already exists and `reset` is False, so an
    existing database is never dropped by accident.
    """
    url = make_url(database_url)
    db_name = url.database
    if not db_name:
        raise ValueError("database_url must name a database, e.g. .../agentdb")

    server_engine = create_engine(_server_url(url), isolation_level="AUTOCOMMIT")
    try:
        with server_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = :name"),
                {"name": db_name},
            ).scalar()
            if exists and reset:
                conn.execute(text(f"DROP DATABASE `{db_name}`"))
                exists = 0
            if exists:
                # Images such as the official MySQL container create an empty database for us.
                # Building into an empty database is fine; a database that already has tables is not.
                table_count = conn.execute(
                    text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :name"),
                    {"name": db_name},
                ).scalar()
                if table_count:
                    raise RuntimeError(f"Database '{db_name}' already has tables. Pass reset=True to rebuild it.")
                # Procedure variables take the database's default collation, so it must match the
                # collation the schema uses. Otherwise comparisons between them fail at run time.
                conn.execute(text(f"ALTER DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            else:
                conn.execute(text(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    finally:
        server_engine.dispose()

    # The SQL files hard-code the name `agentdb`; retarget them to the requested database.
    name_pattern = re.compile(r"\bagentdb\b")
    target_engine = create_engine(url)
    try:
        raw = target_engine.raw_connection()
        try:
            cursor = raw.cursor()
            for path in ordered_files(include_seed):
                if not path.exists():
                    continue
                script = name_pattern.sub(db_name, path.read_text(encoding="utf-8"))
                for statement in split_sql(script):
                    cursor.execute(statement)
            raw.commit()
        finally:
            raw.close()
    finally:
        target_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an AgentDB MySQL database from database/*.sql")
    parser.add_argument("--url", default=settings.sqlalchemy_database_url, help="SQLAlchemy URL including the database name")
    parser.add_argument("--seed", action="store_true", help="also load database/seed.sql")
    parser.add_argument("--reset", action="store_true", help="drop the database first if it exists")
    parser.add_argument("--if-missing", action="store_true", help="do nothing if the schema is already built (safe for container start-up)")
    args = parser.parse_args()
    if args.if_missing and schema_is_built(args.url):
        print("Schema already built; nothing to do.")
        return
    build_database(args.url, include_seed=args.seed, reset=args.reset)
    print(f"Database built from {DATABASE_DIR} (seed={'yes' if args.seed else 'no'}).")


if __name__ == "__main__":
    main()
