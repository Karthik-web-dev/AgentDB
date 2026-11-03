-- =============================================================================
-- Novelty 5: Latency anomaly detection in SQL (rolling z-score)
-- =============================================================================
-- For every completed run, the baseline is the mean and standard deviation of the
-- previous 20 completed runs of the same agent (the current run is excluded, so a spike
-- is never compared against itself). A run is flagged when |z| >= threshold.
-- Everything is computed with window functions inside MySQL: no external ML service.
--
-- A "flat baseline" (every previous run had the same latency) has zero deviation, so the
-- z-score is undefined. Such a run is flagged when its latency differs from the baseline.
--
-- Components:
--   v_run_latency_baseline      rolling mean / stddev / sample size per run
--   v_run_latency_zscore        z-score per run, only where the baseline has >= 5 runs
--   sp_detect_latency_anomalies() ownership-scoped detection query, called by the API
-- =============================================================================

CREATE OR REPLACE VIEW v_run_latency_baseline AS
SELECT
    r.id AS run_id,
    r.agent_id,
    r.started_at,
    r.execution_time_ms AS latency_ms,
    COUNT(r.execution_time_ms) OVER w AS baseline_size,
    AVG(r.execution_time_ms) OVER w AS baseline_mean,
    STDDEV_SAMP(r.execution_time_ms) OVER w AS baseline_stddev
FROM runs r
WHERE r.status = 'completed'
  AND r.execution_time_ms IS NOT NULL
WINDOW w AS (
    PARTITION BY r.agent_id
    ORDER BY r.started_at, r.id
    ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
);

CREATE OR REPLACE VIEW v_run_latency_zscore AS
SELECT
    run_id,
    agent_id,
    started_at,
    latency_ms,
    baseline_size,
    baseline_mean,
    baseline_stddev,
    (latency_ms - baseline_mean) / NULLIF(baseline_stddev, 0) AS z_score
FROM v_run_latency_baseline
WHERE baseline_size >= 5;

DELIMITER //

CREATE PROCEDURE sp_detect_latency_anomalies(
    IN p_user_id INT,
    IN p_agent_id INT,        -- NULL means every agent owned by the user
    IN p_z_threshold DOUBLE,
    IN p_since DATETIME
)
BEGIN
    SELECT
        z.run_id,
        z.agent_id,
        z.started_at,
        z.latency_ms,
        ROUND(z.baseline_mean, 2) AS baseline_mean_ms,
        ROUND(z.baseline_stddev, 2) AS baseline_stddev_ms,
        z.baseline_size,
        ROUND(z.z_score, 3) AS z_score,
        CASE
            WHEN z.z_score IS NOT NULL THEN 'z_score'
            ELSE 'flat_baseline'
        END AS detection_reason
    FROM v_run_latency_zscore z
    JOIN agents g ON g.id = z.agent_id
    WHERE g.user_id = p_user_id
      AND (p_agent_id IS NULL OR z.agent_id = p_agent_id)
      AND z.started_at >= p_since
      AND (
            ABS(z.z_score) >= p_z_threshold
            OR (z.z_score IS NULL AND z.baseline_stddev = 0 AND z.latency_ms <> z.baseline_mean)
          )
    ORDER BY z.started_at DESC, z.run_id DESC;
END//

DELIMITER ;
