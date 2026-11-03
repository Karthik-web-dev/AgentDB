# How to Run AgentDB

AgentDB is a web dashboard for recording and analyzing AI-agent activity, with an
optional OpenRouter-powered chat runner and persistent per-agent conversation context.
You can start the complete app with Docker, or run the API and frontend locally against
a MySQL database.

## Option A: Run the full stack with Docker (recommended)

### Requirements

- Docker Desktop (Windows/macOS) or Docker Engine with the Docker Compose plugin
- Git, if you are cloning the repository

### Start

From the repository root:

1. Create the environment file:

   ```powershell
   Copy-Item .env.docker.example .env
   ```

2. Edit `.env` and set `MYSQL_ROOT_PASSWORD` and `SECRET_KEY`. Use a random secret of
   at least 32 characters for `SECRET_KEY`. Keep the MySQL password as its original
   literal value; do not replace `@` with `%40` in this variable.

3. To enable model chat, also set `OPENROUTER_API_KEY` in `.env`. The default base URL is
   `https://openrouter.ai/api/v1`. The key is passed to the backend as an environment
   variable and is not saved in MySQL. Leave it blank if you only want the observability
   dashboard.

4. Build and start the services:

   ```powershell
   docker compose up -d --build
   ```

5. Open [http://localhost:8080](http://localhost:8080). Sign in with the demo account:
   `demo@agentdb.dev` / `demo-password-123`, or register a new account.

Useful URLs:

- App: [http://localhost:8080](http://localhost:8080)
- API documentation: [http://localhost:8080/docs](http://localhost:8080/docs)
- API health: [http://localhost:8080/health](http://localhost:8080/health)

On its first start, the backend initializes MySQL and loads demo data. The database is
stored in the `agentdb-data` Docker volume and remains between restarts. Stop the stack
without deleting data using `docker compose down`. To delete the database volume and
all its data, use `docker compose down -v`.

## Option B: Run the API and frontend locally

### Requirements

- Python 3.11 or newer
- Node.js and npm
- MySQL 8.0.16 or newer

Configure the MySQL server before bootstrapping the schema. AgentDB creates MySQL
functions/triggers and scheduled events. As a MySQL administrator, enable:

```sql
SET GLOBAL log_bin_trust_function_creators = 1;
SET GLOBAL event_scheduler = ON;
```

For persistent settings, put these under `[mysqld]` in the MySQL configuration file:

```ini
log_bin_trust_function_creators = 1
event_scheduler = ON
```

### Backend setup

In PowerShell, from the repository root:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set:

- `SECRET_KEY`: a random string of at least 32 characters
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`: MySQL connection
  settings. The password is safely URL-encoded by the application.

If you plan to run tests, also set `TEST_DATABASE_URL` to a separate disposable database
whose name ends in `_test`. Tests rebuild that database.

Initialize the schema and demo data (run from `backend`):

```powershell
.\.venv\Scripts\python.exe -m app.db.bootstrap --url "mysql+pymysql://user:password@localhost:3306/agentdb" --seed
```

For model chat, set `OPENROUTER_API_KEY` in `backend/.env`. Optional settings are
`OPENROUTER_BASE_URL`, `OPENROUTER_SITE_URL`, `OPENROUTER_APP_NAME`, and
`AGENT_MEMORY_MESSAGES` (maximum recent messages considered),
`AGENT_MEMORY_RECENT_MAX_CHARS` (recent context character cap),
`AGENT_MEMORY_SUMMARY_MAX_CHARS` (summary safety buffer; default 5,000 characters), and
`AGENT_MEMORY_SUMMARIZE_CHUNK_CHARS` (summarizer input chunk size; default 5,000 characters), and
`LLM_MAX_OUTPUT_TOKENS` (model response limit). The raw
conversation remains stored; older turns are summarized separately and recent turns are
sent verbatim. Agent Chat reports an approximate character-based reduction for each run.
Register an agent with an OpenRouter model ID, then open **Agent Chat**. Each user and
assistant message is retained in MySQL and recent turns are reused as context. The
complete conversation is visible in Agent Chat; only the configured recent-message
window is sent to the provider each time.

Start the API in this terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs); health is at
[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

### Frontend setup

Open a second terminal at the repository root:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the URL Vite prints (normally [http://127.0.0.1:5173](http://127.0.0.1:5173)).

## Stopping and restarting

- Docker: `docker compose down`; restart with `docker compose up -d`.
- Local API/frontend: press `Ctrl+C` in each terminal. Start the API and Vite commands
  again to resume. The MySQL database retains its data.

## Troubleshooting

- **Backend exits because settings are missing:** check that `backend/.env` exists and
  includes `SECRET_KEY` and `DATABASE_URL`.
- **MySQL refuses to create a function or trigger:** enable
  `log_bin_trust_function_creators` as described above.
- **Scheduled partition maintenance or hourly rollups do not run:** enable MySQL's
  `event_scheduler`.
- **Port already in use:** stop the process using port 8080 (Docker), 8000 (API), or
  5173 (Vite), or adjust the relevant port configuration.
- **Database connection fails:** confirm MySQL is running and that the database name,
  username, password, host, and port in `DATABASE_URL` are correct.

For fuller database setup notes, see [`docs/setup.md`](docs/setup.md).
