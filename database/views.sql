USE agentdb;

-- 1. Agent Performance View: Pre-aggregates run metrics, success rates, average latency, and error counts per agent
CREATE OR REPLACE VIEW agent_performance_view AS
SELECT 
    a.id AS agent_id,
    a.name AS agent_name,
    a.model AS agent_model,
    a.environment AS environment,
    a.status AS agent_status,
    COUNT(r.id) AS total_runs,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS successful_runs,
    SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) AS failed_runs,
    ROUND(
        COALESCE(
            (SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) * 100.0) / NULLIF(COUNT(r.id), 0), 
            0
        ), 2
    ) AS success_rate_pct,
    ROUND(COALESCE(AVG(r.execution_time_ms), 0), 2) AS average_latency_ms,
    COALESCE(l_stats.total_logs, 0) AS total_logs,
    COALESCE(l_stats.error_logs, 0) AS error_logs
FROM agents a
LEFT JOIN runs r ON a.id = r.agent_id
LEFT JOIN (
    SELECT 
        agent_id,
        COUNT(*) AS total_logs,
        SUM(CASE WHEN severity IN ('ERROR', 'CRITICAL') THEN 1 ELSE 0 END) AS error_logs
    FROM logs
    GROUP BY agent_id
) l_stats ON a.id = l_stats.agent_id
GROUP BY a.id, a.name, a.model, a.environment, a.status, l_stats.total_logs, l_stats.error_logs;

-- 2. Recent Errors View: Provides detailed recent failure and critical log records with context
CREATE OR REPLACE VIEW recent_errors_view AS
SELECT 
    l.id AS log_id,
    l.severity,
    l.message,
    l.metadata,
    l.timestamp AS log_timestamp,
    a.id AS agent_id,
    a.name AS agent_name,
    r.id AS run_id,
    r.status AS run_status,
    r.error_message AS run_error_message,
    t.id AS task_id,
    t.title AS task_title
FROM logs l
JOIN agents a ON l.agent_id = a.id
JOIN runs r ON l.run_id = r.id
LEFT JOIN tasks t ON r.task_id = t.id
WHERE l.severity IN ('ERROR', 'CRITICAL')
ORDER BY l.timestamp DESC;

-- 3. Agent Health View: Summarizes health status and 24-hour error frequency for monitoring dashboards
CREATE OR REPLACE VIEW agent_health_view AS
SELECT 
    a.id AS agent_id,
    a.name AS agent_name,
    a.status AS current_status,
    MAX(r.started_at) AS last_run_timestamp,
    COUNT(r.id) AS total_executions,
    SUM(CASE WHEN r.started_at >= NOW() - INTERVAL 24 HOUR AND r.status = 'failed' THEN 1 ELSE 0 END) AS failures_last_24h,
    CASE 
        WHEN a.status = 'inactive' THEN 'DISABLED'
        WHEN SUM(CASE WHEN r.started_at >= NOW() - INTERVAL 24 HOUR AND r.status = 'failed' THEN 1 ELSE 0 END) > 5 THEN 'UNHEALTHY'
        WHEN SUM(CASE WHEN r.started_at >= NOW() - INTERVAL 24 HOUR AND r.status = 'failed' THEN 1 ELSE 0 END) > 0 THEN 'DEGRADED'
        ELSE 'HEALTHY'
    END AS health_status
FROM agents a
LEFT JOIN runs r ON a.id = r.agent_id
GROUP BY a.id, a.name, a.status;
