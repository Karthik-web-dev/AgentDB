USE agentdb;

DELIMITER //

-- 1. Get Agent Statistics within a date range
DROP PROCEDURE IF EXISTS sp_get_agent_statistics //
CREATE PROCEDURE sp_get_agent_statistics(
    IN p_agent_id INT,
    IN p_start_date DATETIME,
    IN p_end_date DATETIME
)
BEGIN
    SELECT 
        a.id AS agent_id,
        a.name AS agent_name,
        COUNT(r.id) AS total_runs,
        SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS successful_runs,
        SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) AS failed_runs,
        ROUND(
            COALESCE(
                (SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) * 100.0) / NULLIF(COUNT(r.id), 0), 
                0
            ), 2
        ) AS success_rate_pct,
        ROUND(COALESCE(AVG(r.execution_time_ms), 0), 2) AS avg_execution_time_ms,
        MIN(r.execution_time_ms) AS min_execution_time_ms,
        MAX(r.execution_time_ms) AS max_execution_time_ms
    FROM agents a
    LEFT JOIN runs r ON a.id = r.agent_id AND r.started_at BETWEEN p_start_date AND p_end_date
    WHERE a.id = p_agent_id
    GROUP BY a.id, a.name;
END //

-- 2. Get Paginated Logs by Agent and Severity
DROP PROCEDURE IF EXISTS sp_get_logs_by_agent //
CREATE PROCEDURE sp_get_logs_by_agent(
    IN p_agent_id INT,
    IN p_severity VARCHAR(20),
    IN p_limit INT,
    IN p_offset INT
)
BEGIN
    SELECT 
        l.id AS log_id,
        l.run_id,
        l.agent_id,
        l.severity,
        l.message,
        l.metadata,
        l.timestamp
    FROM logs l
    WHERE l.agent_id = p_agent_id
      AND (p_severity IS NULL OR p_severity = '' OR l.severity = p_severity)
    ORDER BY l.timestamp DESC
    LIMIT p_limit OFFSET p_offset;
END //

-- 3. Generate Daily Operational Report
DROP PROCEDURE IF EXISTS sp_generate_daily_report //
CREATE PROCEDURE sp_generate_daily_report(
    IN p_report_date DATE
)
BEGIN
    SELECT 
        p_report_date AS report_date,
        COUNT(DISTINCT r.id) AS total_runs_today,
        COUNT(DISTINCT r.agent_id) AS active_agents_today,
        SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS completed_runs,
        SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) AS failed_runs,
        ROUND(
            COALESCE(
                (SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) * 100.0) / NULLIF(COUNT(r.id), 0),
                0
            ), 2
        ) AS error_rate_pct,
        ROUND(COALESCE(AVG(r.execution_time_ms), 0), 2) AS avg_latency_ms,
        (SELECT COUNT(*) FROM logs WHERE DATE(timestamp) = p_report_date AND severity IN ('ERROR', 'CRITICAL')) AS total_critical_errors
    FROM runs r
    WHERE DATE(r.started_at) = p_report_date;
END //

DELIMITER ;
