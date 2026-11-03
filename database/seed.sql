USE agentdb;

-- Clear existing data in correct FK order
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE audit_logs;
TRUNCATE TABLE alerts;
TRUNCATE TABLE metrics;
TRUNCATE TABLE logs;
TRUNCATE TABLE events;
TRUNCATE TABLE runs;
TRUNCATE TABLE tasks;
TRUNCATE TABLE agents;
TRUNCATE TABLE users;
SET FOREIGN_KEY_CHECKS = 1;

-- 1. Insert Users
INSERT INTO users (id, email, password_hash, full_name, role, created_at) VALUES
(1, 'admin@agentdb.io', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeg6Lruj3vjPGga31lW', 'Admin User', 'admin', '2026-09-01 10:00:00'),
(2, 'dev@agentdb.io', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeg6Lruj3vjPGga31lW', 'Developer User', 'developer', '2026-09-01 10:30:00');

-- 2. Insert Agents
INSERT INTO agents (id, user_id, name, description, model, environment, status, version, created_at) VALUES
(1, 1, 'FraudDetectorAgent', 'Monitors transaction streams and identifies anomaly patterns using classification algorithms.', 'gpt-4o', 'production', 'active', '1.2.0', '2026-09-02 08:00:00'),
(2, 1, 'CodeReviewerAgent', 'Performs automated static code analysis, security auditing, and style linting on pull requests.', 'claude-3-5-sonnet', 'production', 'active', '2.0.1', '2026-09-02 09:15:00'),
(3, 2, 'DocSummarizerAgent', 'Summarizes lengthy PDF documents and converts unstructured text to JSON knowledge graphs.', 'gpt-4o-mini', 'staging', 'active', '1.0.0', '2026-09-03 11:20:00'),
(4, 2, 'DataPipelineAgent', 'ETL workflow orchestrator for aggregating raw logs into analytics reporting tables.', 'custom-llama3', 'development', 'maintenance', '0.9.0', '2026-09-04 14:00:00');

-- 3. Insert Tasks
INSERT INTO tasks (id, agent_id, title, description, status, priority, created_at) VALUES
(1, 1, 'Analyze Batch TX-9041', 'Evaluate 50,000 credit card transaction events for fraudulent risk scores.', 'completed', 'high', '2026-09-10 09:00:00'),
(2, 1, 'Real-time Stream Audit', 'Continuous risk monitoring on live API gateway endpoint.', 'in_progress', 'critical', '2026-09-11 08:00:00'),
(3, 2, 'Audit PR #142 - Auth Module', 'Perform security and vulnerability scan on authentication refactoring PR.', 'completed', 'high', '2026-09-10 14:00:00'),
(4, 2, 'Lint Repository Repos', 'Nightly code sanity check across microservices.', 'failed', 'medium', '2026-09-11 01:00:00'),
(5, 3, 'Summarize Q3 Financial Report', 'Extract key financial indicators from 120-page quarterly SEC filing.', 'completed', 'medium', '2026-09-11 10:00:00'),
(6, 4, 'Aggregate Log Tables', 'Consolidate raw log records into daily analytics partitions.', 'pending', 'low', '2026-09-11 12:00:00');

-- 4. Insert Runs (Executions)
-- Note: task_id and agent_id must correspond to tasks(id, agent_id)
INSERT INTO runs (id, task_id, agent_id, status, started_at, completed_at, execution_time_ms, error_message) VALUES
(1, 1, 1, 'completed', '2026-09-10 09:01:00', '2026-09-10 09:03:15', 135000, NULL),
(2, 2, 1, 'completed', '2026-09-11 08:05:00', '2026-09-11 08:06:20', 80000, NULL),
(3, 2, 1, 'running', '2026-09-11 21:00:00', NULL, NULL, NULL),
(4, 3, 2, 'completed', '2026-09-10 14:05:00', '2026-09-10 14:07:30', 150000, NULL),
(5, 4, 2, 'failed', '2026-09-11 01:05:00', '2026-09-11 01:05:42', 42000, 'SyntaxError: Unexpected token in AST parser module line 142'),
(6, 5, 3, 'completed', '2026-09-11 10:02:00', '2026-09-11 10:04:10', 130000, NULL),
(7, NULL, 1, 'completed', '2026-09-11 15:00:00', '2026-09-11 15:01:15', 75000, NULL),
(8, NULL, 2, 'failed', '2026-09-11 16:30:00', '2026-09-11 16:30:18', 18000, 'RateLimitError: API quota exceeded for model claude-3-5-sonnet');

-- 5. Insert Events
INSERT INTO events (id, run_id, event_type, event_name, payload, timestamp) VALUES
(1, 1, 'tool_call', 'invoke_classifier', '{"algorithm": "XGBoost", "batch_size": 50000}', '2026-09-10 09:01:10'),
(2, 1, 'completion', 'fraud_scan_finished', '{"anomalies_detected": 14, "risk_score_max": 0.94}', '2026-09-10 09:03:10'),
(3, 4, 'api_request', 'fetch_pr_diff', '{"pr_id": 142, "files_changed": 18}', '2026-09-10 14:05:15'),
(4, 4, 'tool_call', 'static_analyzer', '{"ruleset": "OWASP-Top-10", "issues_found": 0}', '2026-09-10 14:07:00'),
(5, 5, 'api_request', 'parse_ast', '{"file": "backend/auth/jwt.py"}', '2026-09-11 01:05:20'),
(6, 5, 'error_event', 'ast_parser_failure', '{"line": 142, "char": 18}', '2026-09-11 01:05:40'),
(7, 8, 'api_request', 'anthropic_completion', '{"model": "claude-3-5-sonnet", "tokens": 4096}', '2026-09-11 16:30:05');

-- 6. Insert Logs
INSERT INTO logs (id, run_id, agent_id, severity, message, metadata, timestamp) VALUES
(1, 1, 1, 'INFO', 'Starting batch risk classification scan for Batch TX-9041.', '{"batch_id": "TX-9041"}', '2026-09-10 09:01:02'),
(2, 1, 1, 'WARNING', 'High risk score flagged on transaction TX-9041-8842.', '{"tx_id": "TX-9041-8842", "score": 0.94}', '2026-09-10 09:02:15'),
(3, 1, 1, 'INFO', 'Batch risk classification finished successfully.', '{"processed": 50000, "flagged": 14}', '2026-09-10 09:03:14'),
(4, 4, 2, 'INFO', 'Static security audit started for PR #142.', '{"pr": 142}', '2026-09-10 14:05:05'),
(5, 4, 2, 'INFO', 'Security analysis passed with 0 vulnerabilities.', '{"vulnerabilities": 0}', '2026-09-10 14:07:25'),
(6, 5, 2, 'INFO', 'Starting nightly repository linting task.', '{"target": "all"}', '2026-09-11 01:05:02'),
(7, 5, 2, 'ERROR', 'Syntax error encountered during AST parsing of jwt.py.', '{"file": "jwt.py", "line": 142}', '2026-09-11 01:05:41'),
(8, 8, 2, 'CRITICAL', 'API call failed due to provider rate limit quota exhaustion.', '{"provider": "Anthropic", "status_code": 429}', '2026-09-11 16:30:17');

-- 7. Insert Metrics
INSERT INTO metrics (id, run_id, metric_name, metric_value, unit, timestamp) VALUES
(1, 1, 'latency_ms', 135000, 'ms', '2026-09-10 09:03:15'),
(2, 1, 'prompt_tokens', 12400, 'tokens', '2026-09-10 09:03:15'),
(3, 1, 'completion_tokens', 1850, 'tokens', '2026-09-10 09:03:15'),
(4, 4, 'latency_ms', 150000, 'ms', '2026-09-10 14:07:30'),
(5, 4, 'cost_usd', 0.184, 'USD', '2026-09-10 14:07:30'),
(6, 5, 'latency_ms', 42000, 'ms', '2026-09-11 01:05:42'),
(7, 8, 'latency_ms', 18000, 'ms', '2026-09-11 16:30:18');

-- 8. Insert Alerts
-- Note: agent_id = 1 targets FraudDetectorAgent specifically; agent_id = NULL applies globally across all agents.
INSERT INTO alerts (id, user_id, agent_id, rule_name, metric_name, condition_operator, threshold_value, time_window_minutes, status, created_at) VALUES
(1, 1, 1, 'High Execution Latency Alert', 'latency_ms', '>', 100000, 15, 'active', '2026-09-05 10:00:00'),
(2, 1, 2, 'High Failure Rate Alert', 'error_rate', '>', 10.0, 30, 'active', '2026-09-05 10:05:00'),
(3, 2, NULL, 'Global API Cost Limit Warning', 'cost_usd', '>', 1.00, 60, 'disabled', '2026-09-06 14:00:00');

-- 9. Insert Audit Logs
INSERT INTO audit_logs (id, user_id, action, entity_type, entity_id, details, timestamp) VALUES
(1, 1, 'CREATE_AGENT', 'agents', 1, '{"name": "FraudDetectorAgent", "model": "gpt-4o"}', '2026-09-02 08:00:00'),
(2, 1, 'CREATE_AGENT', 'agents', 2, '{"name": "CodeReviewerAgent", "model": "claude-3-5-sonnet"}', '2026-09-02 09:15:00'),
(3, 2, 'CREATE_AGENT', 'agents', 3, '{"name": "DocSummarizerAgent", "model": "gpt-4o-mini"}', '2026-09-03 11:20:00'),
(4, 1, 'RUN_FAILED', 'runs', 5, '{"error": "SyntaxError in AST parser"}', '2026-09-11 01:05:42');
