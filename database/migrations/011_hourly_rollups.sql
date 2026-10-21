-- =============================================================================
-- Novelty 10: Incrementally refreshed hourly rollups per agent
-- =============================================================================
-- Dashboards should not scan every run on every page load. agent_hourly_stats keeps one row
-- per (agent, hour) with exact aggregates. Latency is stored as a sum and a count rather than
-- an average, so averages stay exact when hours are combined.
--
-- sp_refresh_hourly_stats(since) recomputes every hour from `since` onward. Recomputing a
-- bucket replaces its values, so the refresh is idempotent and also picks up runs whose
-- status changed after the bucket was first written.
--
-- Freshness: ev_refresh_hourly_stats re-aggregates the last two hours every hour. Callers
-- that need an exact figure for a range call the same procedure for that range first
-- (the overview endpoint does this).
--
-- Requires event_scheduler = ON for the scheduled refresh (see docs/setup.md).
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_hourly_stats (
    agent_id INT NOT NULL,
    bucket_start DATETIME NOT NULL,
    runs_total INT UNSIGNED NOT NULL,
    runs_completed INT UNSIGNED NOT NULL,
    runs_failed INT UNSIGNED NOT NULL,
    latency_sum_ms BIGINT UNSIGNED NOT NULL DEFAULT 0,
    latency_count INT UNSIGNED NOT NULL DEFAULT 0,
    max_latency_ms INT UNSIGNED NULL,
    refreshed_at DATETIME NOT NULL,
    PRIMARY KEY (agent_id, bucket_start),
    CONSTRAINT fk_agent_hourly_stats_agent FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE RESTRICT,
    CONSTRAINT chk_agent_hourly_stats_on_the_hour CHECK (MINUTE(bucket_start) = 0 AND SECOND(bucket_start) = 0),
    CONSTRAINT chk_agent_hourly_stats_counts CHECK (runs_completed + runs_failed <= runs_total)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DELIMITER //

CREATE PROCEDURE sp_refresh_hourly_stats(IN p_since DATETIME)
BEGIN
    DECLARE v_start DATETIME;
    SET v_start = DATE_FORMAT(p_since, '%Y-%m-%d %H:00:00');

    -- Replace the affected hours wholesale. Re-deriving each hour from runs keeps the
    -- refresh idempotent and corrects buckets whose runs changed status.
    DELETE FROM agent_hourly_stats WHERE bucket_start >= v_start;

    INSERT INTO agent_hourly_stats (
        agent_id, bucket_start, runs_total, runs_completed, runs_failed,
        latency_sum_ms, latency_count, max_latency_ms, refreshed_at
    )
    SELECT
        r.agent_id,
        DATE_FORMAT(r.started_at, '%Y-%m-%d %H:00:00') AS bucket_start,
        COUNT(*),
        SUM(r.status = 'completed'),
        SUM(r.status = 'failed'),
        COALESCE(SUM(CASE WHEN r.status = 'completed' THEN r.execution_time_ms END), 0),
        SUM(CASE WHEN r.status = 'completed' AND r.execution_time_ms IS NOT NULL THEN 1 ELSE 0 END),
        MAX(CASE WHEN r.status = 'completed' THEN r.execution_time_ms END),
        NOW()
    FROM runs r
    WHERE r.started_at >= v_start
    GROUP BY r.agent_id, DATE_FORMAT(r.started_at, '%Y-%m-%d %H:00:00');
END//

DELIMITER ;

CREATE OR REPLACE VIEW v_owned_hourly_stats AS
SELECT s.*
FROM agent_hourly_stats s
JOIN agents a ON a.id = s.agent_id
WHERE a.user_id = fn_current_user_id();

CREATE EVENT ev_refresh_hourly_stats
    ON SCHEDULE EVERY 1 HOUR
    STARTS '2026-01-01 00:05:00'
    DO CALL sp_refresh_hourly_stats(NOW() - INTERVAL 2 HOUR);
