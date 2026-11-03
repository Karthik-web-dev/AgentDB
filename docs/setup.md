# AgentDB backend setup

## Requirements

- Python 3.11 or newer
- MySQL 8.0.16 or newer. CHECK constraints are enforced from 8.0.16, and several integrity
  rules depend on them. The Docker setup below uses MySQL 8.0 and needs nothing installed.

## 1. Configure MySQL

AgentDB's triggers and stored functions are created by the project SQL files. If your MySQL
server writes a binary log (the default on most installs), MySQL refuses to create functions
and triggers unless this setting is on. Run this as an administrator:

```sql
SET GLOBAL log_bin_trust_function_creators = 1;
```

Partition maintenance and hourly rollups run as scheduled MySQL events. Turn the event
scheduler on:

```sql
SET GLOBAL event_scheduler = ON;
```

To keep both settings across restarts, put them in the MySQL configuration file:

```ini
[mysqld]
log_bin_trust_function_creators = 1
event_scheduler = ON
```

## 2. Create the Python environment

```bash
cd backend
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS or Linux, use `.venv/bin/python -m pip install -r requirements.txt`.

## 3. Configure the environment

Copy `backend/.env.example` to `backend/.env` and fill in:

- `SECRET_KEY`: a random string of at least 32 characters. Generate one with
  `python -c "import secrets; print(secrets.token_hex(32))"`.
- `DATABASE_URL`: for example `mysql+pymysql://user:password@localhost:3306/agentdb`
- `TEST_DATABASE_URL`: the same server with a database name ending in `_test`. The test
  suite drops and rebuilds that database, so never point it at real data.

`backend/.env` is ignored by git. Never commit it.

## 4. Build the database

From the `backend` directory:

```bash
.venv\Scripts\python.exe -m app.db.bootstrap --url "mysql+pymysql://user:password@localhost:3306/agentdb" --seed
```

This applies, in order: `database/schema.sql`, `indexes.sql`, `views.sql`, `procedures.sql`,
`triggers.sql`, every file in `database/migrations/` (sorted by name), and then `seed.sql`
when `--seed` is given.

To rebuild a database that already exists, add `--reset`. This drops it first and loses all
data.

## 5. Run the API

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- Health check: `http://127.0.0.1:8000/health`
- Interactive API docs: `http://127.0.0.1:8000/docs`
- All endpoints live under `/api/v1`.

## 6. Run the tests

The tests run against a real MySQL server, not mocks. Set `TEST_DATABASE_URL` in `.env`, then:

```bash
.venv\Scripts\python.exe -m pytest -q
```

The first run of each session rebuilds the test database from the same SQL files the
application uses, so the tests exercise the real triggers, views and procedures.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `You do not have the SUPER privilege and binary logging is enabled` | Set `log_bin_trust_function_creators = 1` (step 1). |
| Rollups or partitions are not maintained automatically | The event scheduler is off. Set `event_scheduler = ON`. |
| `audit chain head is missing` on insert | The `audit_chain_head` row was deleted. Rebuild the database with `--reset`. |
| `logs.run_id does not reference an existing run` | Expected: this is the integrity check that replaces the foreign keys on partitioned tables. |

## Run everything with Docker

This starts MySQL, the API and the web app. It needs Docker Desktop (or Docker Engine with the
Compose plugin) and nothing else.

1. Create the environment file at the repository root:

   ```bash
   cp .env.docker.example .env
   ```

   Edit `.env` and set `MYSQL_ROOT_PASSWORD` and `SECRET_KEY`.

2. Build and start the stack:

   ```bash
   docker compose up -d --build
   ```

3. Open the app at `http://localhost:8080` and sign in with the demo account:
   `demo@agentdb.dev` / `demo-password-123`. You can also register your own account.

- The API docs are at `http://localhost:8080/docs`, and the health check at `http://localhost:8080/health`.
- On first start the backend builds the database from the SQL files and loads the demo dataset
  (agents, about 48 hours of runs, failures, alerts, costs, audit records). Later starts keep existing
  data: the build is skipped when the schema exists, and the demo loader does nothing when the demo
  account exists.
- To load the demo data into a local database instead: `python -m app.demo_data` (from `backend`).
- The MySQL data lives in the `agentdb-data` Docker volume. To wipe it, run
  `docker compose down -v`. This deletes all data.
- The database settings the project needs (`log_bin_trust_function_creators`, `event_scheduler`)
  are set in the compose file.
