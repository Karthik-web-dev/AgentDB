AgentDB

AI-Agent Observability & Structured Logging Platform powered by a relational database

AgentDB is a full-stack platform for running OpenRouter-backed agent chats and monitoring executions, events, logs, metrics, alerts, and audit activity through a unified dashboard. Chat messages are persisted per agent and recent turns are reused as model context.

The project is built with React + TypeScript, FastAPI, and MySQL, with the relational database serving as the core of the system. It demonstrates DBMS concepts through a practical application, and includes an optional OpenRouter-backed agent chat flow with persistent per-agent conversation context.

AgentDB also includes an optional OpenRouter chat path. Configure `OPENROUTER_API_KEY` on the backend, register an agent using a provider model ID (for example `openai/gpt-4o-mini`), and use **Agent Chat**. Messages are saved against that agent; older turns are compressed into a bounded summary while recent turns are sent verbatim. The original messages remain stored. See [HOW_TO_RUN.md](HOW_TO_RUN.md) for setup.

🚀 Project Overview

Modern AI-agent systems can involve multiple agents, tasks, executions, database operations, failures, and performance metrics. Tracking all of this through unstructured logs quickly becomes difficult.

AgentDB addresses this problem by providing a structured platform where agent activity can be:

Registered and managed

Organized into tasks and execution runs

Captured as structured events and logs

Measured through performance metrics

Analyzed through dashboards and reports

Monitored through configurable alerts

Tracked through an audit trail

The system combines a modern developer-oriented interface with a carefully designed relational database architecture.

🎯 Objectives

The primary objectives of AgentDB are:

Build a practical full-stack application around a relational database.

Demonstrate advanced DBMS concepts in a real-world scenario.

Provide structured logging for AI-agent executions.

Enable searching, filtering, and analyzing execution data.

Provide performance and failure analytics.

Implement alerts for abnormal agent behavior.

Maintain an audit trail of important system actions.

Demonstrate database integrity, transactions, indexing, views, stored procedures, and triggers.

Provide a clean and presentation-ready developer dashboard.

✨ Key Features

🔐 Authentication

User registration

Secure password hashing

JWT-based authentication

Protected API routes

Authentication-aware frontend routing

🤖 Agent Management

Create agents

Update agents

Delete agents

Activate/deactivate agents

Track versions and environments

View agent-specific performance

📋 Task Management

Create and manage tasks

Associate tasks with agents

Track task execution

⚡ Execution / Run Tracking

Track individual agent runs

Record start and completion times

Calculate execution duration

Track success/failure status

Associate events, logs, and metrics with runs

📝 Structured Log Explorer

Search logs

Filter by severity

Filter by agent

Filter by event type

Filter by date/time

Paginate large datasets

Inspect structured metadata

Track errors and critical events

📊 Analytics

The analytics dashboard provides insights into:

Total agents

Active agents

Total executions

Failed executions

Error rate

Average execution latency

Logs by severity

Agent performance

Failure trends

Events over time

🚨 Alerts

Create configurable rules such as:

Error rate > 10%
Latency > 1000 ms
5 failures within 10 minutes

Alerts can be monitored and managed through the dashboard.

🧾 Audit Trail

Important system activity can be recorded with:

User

Action

Entity

Entity ID

Timestamp

Details

🗄️ Database Explorer

AgentDB includes a visual representation of the relational database structure and relationships between entities.

🏗️ Architecture

                         ┌─────────────────────┐
                         │      AgentDB UI     │
                         │ React + TypeScript  │
                         │ Tailwind + shadcn/ui│
                         └──────────┬──────────┘
                                    │
                              REST API / JSON
                                    │
                         ┌──────────▼──────────┐
                         │       FastAPI       │
                         │     Python API      │
                         │  Auth + Services    │
                         └──────────┬──────────┘
                                    │
                             SQLAlchemy ORM
                                    │
                         ┌──────────▼──────────┐
                         │        MySQL        │
                         │   Relational DB     │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
          Tables                 DBMS Logic           Analytics
              │                     │                     │
        Relationships       Views / Procedures      Aggregations
        Constraints         Triggers                Reports
        Indexes             Transactions

The frontend never connects directly to MySQL. All database operations are handled through the backend API.

🗃️ Database Design

Core entities include:

users
agents
tasks
runs
events
logs
metrics
alerts
audit_logs

Relationship Overview

users
 │
 ├── agents
 │
 ├── alerts
 │
 └── audit_logs

agents
 │
 ├── tasks
 │
 ├── runs
 │
 └── logs

tasks
 │
 └── runs

runs
 │
 ├── events
 ├── logs
 └── metrics

The schema will be normalized and designed to maintain referential integrity.

🧠 DBMS Concepts Demonstrated

AgentDB is specifically designed to demonstrate the following DBMS concepts:

Entity-Relationship Modeling

Relational Schema Design

Normalization

Primary Keys

Foreign Keys

Referential Integrity

NOT NULL constraints

UNIQUE constraints

CHECK constraints

DEFAULT values

One-to-many relationships

SQL Joins

Subqueries

Aggregate functions

GROUP BY

HAVING

Indexing

Database Views

Stored Procedures

Triggers

Transactions

Audit Logging

Query Optimization

Pagination and filtering

Each database feature is intended to serve a practical purpose within the application.

🛠️ Technology Stack

Frontend

Technology

Purpose

React

UI framework

TypeScript

Type-safe development

Vite

Frontend build tooling

Tailwind CSS

Styling

shadcn/ui

UI components

Recharts

Data visualization

Axios

API communication

React Router

Client-side routing

React Hook Form

Form management

Zod

Validation

Lucide

Icons

Backend

Technology

Purpose

Python

Backend language

FastAPI

REST API

SQLAlchemy

ORM

Pydantic

Data validation

Alembic

Database migrations

JWT

Authentication

bcrypt

Password hashing

Database & Infrastructure

Technology

Purpose

MySQL

Relational database

Docker

Containerization

Docker Compose

Multi-container environment

Git

Version control

GitHub

Repository and collaboration

📁 Project Structure

AgentDB/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── layouts/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   ├── utils/
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── repositories/
│   │   └── utils/
│   ├── migrations/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── database/
│   ├── schema.sql
│   ├── seed.sql
│   ├── indexes.sql
│   ├── views.sql
│   ├── procedures.sql
│   └── triggers.sql
│
├── docs/
│   ├── architecture.md
│   ├── database.md
│   ├── api.md
│   ├── dbms-concepts.md
│   └── setup.md
│
├── PROMPT.md
├── PLANNING.md
├── README.md
├── docker-compose.yml
└── .gitignore

🔌 API Structure

The backend API is organized into logical modules:

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

Example endpoints:

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

The API structure may evolve during implementation while preserving the overall architecture.

🔒 Security

AgentDB follows basic application security practices including:

Password hashing

JWT authentication

Protected API routes

Authorization checks

Request validation

SQL injection protection through ORM/query parameterization

Environment-based secrets

CORS configuration

No credentials committed to the repository

Sensitive configuration should be stored in environment variables.

🧪 Testing

The project will include testing for:

Authentication

Agent operations

Task operations

Run creation

Structured logging

Filtering and pagination

Analytics

Alerts

Authorization

Invalid input

Missing resources

Database behavior

Transaction-related operations

Backend tests will primarily use Pytest.

🐳 Running with Docker

Docker Compose runs the whole stack: the React frontend, the FastAPI backend and MySQL.

```
cp .env.docker.example .env      # set MYSQL_ROOT_PASSWORD and SECRET_KEY
docker compose up -d --build
```

Then open http://localhost:8080. The setup guide covers the local (non-Docker) setup, the
database requirements and the test suite:

docs/setup.md

The database design is described in docs/novelties.md (the features built into MySQL) and
docs/query-plans.md (the query plans that are verified by tests).

🚧 Development Roadmap

AgentDB is being developed incrementally.

Day 1 - Foundation + Database

Project scaffolding

Frontend setup

Backend setup

MySQL setup

Database schema

Relationships

Constraints

Indexes

Seed data

Views

Stored procedures

Triggers

Day 2 - Backend + APIs

Authentication

Agent APIs

Task APIs

Run APIs

Event APIs

Log APIs

Metrics

Analytics

Alerts

Audit trail

Backend testing

Day 3 - Frontend + Integration

Application shell

Authentication UI

Dashboard

Agent management

Task management

Run explorer

Log explorer

Analytics

Alerts

Audit trail

Database explorer

Full-stack integration

Day 4 - Finalization

UI polish

Performance optimization

Security review

Testing

Dockerization

Documentation

DBMS verification

End-to-end demonstration

🤖 AI-Assisted Development

AgentDB is being developed using AI-assisted development tools while maintaining a controlled project architecture.

The repository contains:

PROMPT.md
PLANNING.md

PROMPT.md

Defines:

Project identity

Architecture

Technology stack

Database direction

Development rules

AI collaboration rules

Definition of done

PLANNING.md

Defines:

Four-day implementation roadmap

Daily objectives

Implementation order

Verification steps

Collaboration workflow

The repository itself remains the source of truth for the current implementation.

👥 Team

AgentDB is being developed as a collaborative academic project.

Project Repository: GitHub

Team members and contribution details can be added here as the project progresses.

📚 Academic Purpose

AgentDB is developed as a DBMS course project with the goal of demonstrating how database concepts can be applied to a realistic software system.

Rather than implementing isolated SQL examples, the project integrates DBMS concepts into a complete workflow:

Agent
  ↓
Task
  ↓
Execution / Run
  ↓
Events + Logs + Metrics
  ↓
Analytics
  ↓
Alerts
  ↓
Audit Trail

This allows the database concepts to be demonstrated through an actual application and end-to-end data flow.

🔮 Future Scope

Potential future enhancements include:

Real-time log streaming

WebSocket-based monitoring

Advanced anomaly detection

AI-assisted log summarization

Distributed agent monitoring

Role-based access control

Notification integrations

Advanced query builder

Historical performance comparison

Multi-tenant support

These features are outside the initial academic scope unless explicitly added later.

📄 License

This project is developed for academic and educational purposes.

A formal open-source license can be added if the repository is made public.

⭐ AgentDB

Structured data. Observable agents. One relational backbone.
