# AgentDB - Master Project Prompt

## 1. Project Identity

Project Name: AgentDB

AgentDB is a DBMS-focused AI-agent observability and structured logging platform. It is designed as a serious academic DBMS course project, while also being implemented as a polished, usable full-stack application.

The system should allow users to manage AI agents, tasks, executions/runs, structured logs, events, metrics, alerts, and audit records from a single dashboard.

The database is the academic core of the project. The application must demonstrate meaningful relational database design and advanced DBMS concepts rather than being a simple CRUD application.

---

## 2. Most Important Rule

THIS FOLDER IS THE SINGLE SOURCE OF TRUTH FOR THE PROJECT.

All project work must remain inside the project folder.

Do not create project files elsewhere unless explicitly requested.

Before making changes:
1. Inspect the existing folder.
2. Read this `PROMPT.md`.
3. Read `PLANNING.md` when implementation planning is relevant.
4. Inspect existing code before modifying it.
5. Preserve working functionality.
6. Do not rebuild working modules unnecessarily.

Never assume that a feature does not exist until the existing project has been inspected.

---

## 3. Development Philosophy

Build the project incrementally.

Do NOT attempt to generate the entire application in one pass.

The project will be developed in controlled phases:
- Architecture
- Database
- Backend foundation
- Backend APIs
- Frontend foundation
- Frontend modules
- Integration
- Advanced DBMS features
- Testing
- Documentation
- Deployment

Every phase must leave the project in a working state.

Prefer:
- clean architecture
- maintainability
- correctness
- security
- database integrity
- reusable components
- clear naming
- meaningful comments
- tests
- documentation

Avoid:
- unnecessary libraries
- unnecessary microservices
- overengineering
- duplicate functionality
- hardcoded production data
- fake APIs
- fake database logic
- frontend-side SQL
- exposed secrets

---

# 4. Core Technology Stack

## Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- Recharts
- Axios
- React Router
- React Hook Form
- Zod
- Lucide icons

## Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- Alembic
- JWT authentication
- bcrypt/password hashing

## Database

- MySQL

## Infrastructure

- Docker
- Docker Compose
- Git
- GitHub

## Testing

- Pytest for backend
- Appropriate frontend testing where practical

---

# 5. High-Level Architecture

```text
                    AGENTDB
                       |
          +------------+------------+
          |                         |
      FRONTEND                   BACKEND
          |                         |
 React + TypeScript            FastAPI
 Tailwind/shadcn               SQLAlchemy
 Recharts                      Pydantic
 Axios                         JWT
          |                         |
          +-----------API------------+
                       |
                     MySQL
                       |
       +---------------+----------------+
       |               |                |
    Relational      DBMS Logic      Analytics
     Tables        Views/Procedures
                   Triggers/Indexes
                   Transactions
```

The frontend must communicate with the backend through APIs.

The frontend must NEVER directly connect to MySQL.

---

# 6. Main Functional Modules

The application should eventually contain:

1. Authentication
2. Dashboard
3. Agent Management
4. Task Management
5. Run/Execution Management
6. Structured Log Explorer
7. Events
8. Metrics
9. Analytics
10. Alerts
11. Audit Trail
12. Database Relationship Explorer
13. Settings

---

# 7. Database Entities

Core entities:

```text
users
agents
tasks
runs
events
logs
metrics
alerts
audit_logs
```

Expected relationship structure:

```text
users
 |
 +---- agents
 |
 +---- alerts
 |
 +---- audit_logs

agents
 |
 +---- tasks
 |
 +---- runs
 |
 +---- logs

tasks
 |
 +---- runs

runs
 |
 +---- events
 |
 +---- logs
 |
 +---- metrics
```

The exact schema may be refined during database design, but relationships must remain logically consistent.

---

# 8. DBMS Requirements

The project MUST meaningfully demonstrate:

- Primary keys
- Foreign keys
- Referential integrity
- NOT NULL constraints
- UNIQUE constraints
- CHECK constraints where supported
- DEFAULT values
- One-to-many relationships
- Appropriate normalization
- SQL joins
- Aggregation
- GROUP BY
- HAVING
- Subqueries
- Indexing
- Views
- Stored procedures
- Triggers
- Transactions
- Audit logging
- Query optimization
- Pagination/filtering
- Error handling

Do not add DBMS features only for decoration. Each feature should have a practical purpose.

---

# 9. Database Design Direction

Important indexes should be considered for fields frequently used for:

- log searches
- severity filtering
- agent filtering
- run filtering
- event filtering
- timestamp filtering
- status filtering

Examples:

```text
logs.timestamp
logs.severity
logs.agent_id
logs.run_id
events.event_type
runs.status
runs.started_at
```

Indexes must be justified rather than added blindly.

---

# 10. SQL Views

Create meaningful views such as:

### agent_performance_view

Potential fields:

```text
agent_id
agent_name
total_runs
successful_runs
failed_runs
success_rate
average_latency
error_rate
```

### recent_errors_view

Provides recently generated error/critical records.

### agent_health_view

Provides a summarized health state for agents.

The final names can be adjusted during implementation.

---

# 11. Stored Procedures

Create useful procedures such as:

```text
sp_get_agent_statistics
sp_get_logs_by_agent
sp_generate_daily_report
```

Procedures should demonstrate real database-side processing.

---

# 12. Triggers

Use triggers where they provide genuine value.

Examples:

### Audit trigger

Changes to important entities create audit records.

### Run completion logic

Important state transitions can automatically record completion information.

### Alert-related logic

Threshold-related database events may generate alerts where appropriate.

Do not create excessive or redundant triggers.

---

# 13. Transactions

Operations involving multiple dependent database writes should use transactions.

Example:

```text
BEGIN
  Create Run
  Create initial Event
  Create initial Log
  Create Metrics record
COMMIT
```

If a required operation fails:

```text
ROLLBACK
```

Atomicity and consistency should be preserved.

---

# 14. Backend Architecture

Recommended structure:

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── security.py
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   ├── services/
│   ├── repositories/
│   └── utils/
├── migrations/
├── tests/
├── requirements.txt
├── Dockerfile
└── .env
```

Use separation between:
- API routes
- validation schemas
- database models
- business logic
- database access where useful

Do not put all backend logic inside `main.py`.

---

# 15. Backend API Direction

Expected API groups:

```text
/auth
/agents
/tasks
/runs
/logs
/events
/metrics
/analytics
/alerts
/audit
```

Example endpoints:

```text
POST   /auth/register
POST   /auth/login
GET    /auth/me

GET    /agents
POST   /agents
GET    /agents/{id}
PUT    /agents/{id}
DELETE /agents/{id}

GET    /tasks
POST   /tasks
GET    /tasks/{id}

GET    /runs
POST   /runs
GET    /runs/{id}

GET    /logs
GET    /logs/{id}

GET    /events
GET    /metrics

GET    /analytics/overview
GET    /analytics/agents
GET    /analytics/errors
GET    /analytics/latency

GET    /alerts
POST   /alerts
PUT    /alerts/{id}
DELETE /alerts/{id}

GET    /audit
```

The exact endpoint design may be refined when implementation begins.

---

# 16. API Rules

Use:
- proper HTTP methods
- proper HTTP status codes
- request validation
- authentication dependencies
- pagination
- filtering
- consistent error handling

Do not expose database internals unnecessarily.

Preferred response pattern:

```json
{
  "success": true,
  "data": {},
  "message": "Operation completed successfully"
}
```

Error pattern:

```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Requested resource was not found"
  }
}
```

---

# 17. Authentication

Implement:

```text
Register
  ↓
Password hashing
  ↓
Store user
  ↓
Login
  ↓
Verify password
  ↓
Generate JWT
  ↓
Authenticated API requests
```

Never store plaintext passwords.

Never put JWT secrets or database credentials in frontend code.

Use environment variables for secrets/configuration.

---

# 18. Frontend Architecture

Recommended structure:

```text
frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── layouts/
│   ├── hooks/
│   ├── services/
│   ├── types/
│   ├── utils/
│   ├── lib/
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── vite.config.ts
```

Build reusable components rather than duplicating UI.

---

# 19. Frontend Design Direction

The application should look like a modern developer/observability platform.

Desired characteristics:

- professional
- dark-first or polished dark/light system
- clean dashboard
- strong typography
- compact data tables
- charts
- status indicators
- searchable logs
- expandable records
- responsive layout
- clear navigation
- subtle animations
- excellent empty/loading/error states

Do not turn it into a generic template dashboard.

---

# 20. Main Frontend Pages

## Dashboard

Show:

- total agents
- active agents
- total runs
- failed runs
- error rate
- average execution time
- execution trend
- agent health
- recent errors

## Agents

Show:
- agent table
- create/edit agent
- status
- version
- environment
- model
- performance

## Agent Details

Tabs:

```text
Overview
Runs
Logs
Events
Metrics
```

Show an execution timeline.

## Tasks

Manage agent tasks.

## Runs

Show:

```text
Run ID
Agent
Task
Started
Completed
Duration
Status
Error
```

Allow filtering.

## Log Explorer

Must support:
- search
- severity filter
- agent filter
- event filter
- date filter
- environment filter
- pagination
- expandable structured metadata

## Analytics

Charts for:
- log severity
- execution latency
- failure rate
- events over time
- agent performance
- problematic agents

## Alerts

Allow creation and management of threshold-based rules.

Examples:

```text
error rate > 10%
latency > 1000ms
5 failures within 10 minutes
```

## Audit Trail

Display:
- user
- action
- entity
- entity ID
- timestamp
- details

## Database Explorer

Show a visual representation of the project's relational entities and relationships.

---

# 21. Structured Logs

Logs should support structured fields rather than only text.

Conceptual example:

```json
{
  "timestamp": "2026-09-11T21:00:00",
  "agent": "FraudDetector",
  "event": "prediction_completed",
  "severity": "INFO",
  "metadata": {
    "transaction_id": "TX123",
    "latency": 184,
    "model": "XGBoost"
  }
}
```

The schema must be designed carefully so relational querying remains useful.

Do not blindly put the entire database into one JSON column.

---

# 22. Security Requirements

At minimum:

- password hashing
- JWT authentication
- authorization checks
- input validation
- SQL injection prevention
- environment variables
- CORS configuration
- safe error messages
- no secrets committed to Git
- protected endpoints
- appropriate database permissions where practical

---

# 23. Testing Requirements

Backend tests should cover:

- authentication
- agent CRUD
- task CRUD
- run creation
- log retrieval
- filters
- analytics
- alerts
- authorization
- invalid input
- missing resources
- transaction behavior where practical

Test database behavior where practical.

---

# 24. Docker

Eventually provide:

```text
frontend container
backend container
mysql container
```

with Docker Compose.

Do not introduce Docker complexity before the local application works.

---

# 25. Documentation

Final project should contain:

```text
README.md
docs/
├── architecture.md
├── database.md
├── api.md
├── dbms-concepts.md
└── setup.md
```

Documentation should explain why DBMS concepts were used.

The project should be easy for another student/evaluator to run.

---

# 26. Git Rules

Create checkpoints frequently.

Before major changes:

```bash
git add .
git commit -m "checkpoint: before <feature>"
```

Use meaningful commits.

Never delete or overwrite working functionality without understanding its purpose.

---

# 27. AI Agent Collaboration Rules

This project is being built using multiple AI development tools.

Therefore:

1. Treat the project folder as shared state.
2. Never assume another AI tool has not modified files.
3. Always inspect current files.
4. Read project documentation before coding.
5. Never blindly overwrite another agent's work.
6. Avoid simultaneous edits to the same files when possible.
7. After completing a feature, update relevant documentation.
8. Keep the project runnable after each milestone.
9. Report what changed.
10. Report tests performed.
11. Report any known limitations.
12. If an architectural decision is uncertain, stop and document the decision rather than silently changing architecture.

---

# 28. Definition of Done

A feature is NOT complete merely because code exists.

A feature is complete only when:

- implementation exists
- integration works
- validation works
- error states work
- relevant tests pass
- database integrity is preserved
- frontend/backend integration works where applicable
- documentation is updated where necessary

---

# 29. Final Academic Goal

The finished AgentDB project should allow the team to confidently demonstrate:

```text
ER Modeling
↓
Relational Schema
↓
Normalization
↓
Constraints
↓
Relationships
↓
SQL Queries
↓
Joins
↓
Subqueries
↓
Indexes
↓
Views
↓
Stored Procedures
↓
Triggers
↓
Transactions
↓
Audit Logging
↓
Query Optimization
↓
Full-stack Application
```

The application should look modern, but the DBMS architecture must remain the foundation.

Do not sacrifice database quality for visual effects.

---

# 30. Final Instruction

Do not attempt to finish everything immediately.

Follow the current day's task from `PLANNING.md`.

At the end of each work session:
- verify the current state
- run relevant tests/checks
- document completed work
- identify remaining work
- do not start future phases unless explicitly instructed

The goal is a stable, polished, academically strong AgentDB project built deliberately over multiple stages.
