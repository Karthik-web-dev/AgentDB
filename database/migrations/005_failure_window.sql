-- =============================================================================
-- Novelty 4: Sliding-window failure rules ("N failures within M minutes")
-- =============================================================================
-- A failure_window rule counts failed runs in the last time_window_minutes, for the
-- rule's scope (one agent, or all agents of the rule's owner). The check runs inside
-- the transaction that marks the run failed, so the failing run is always counted.
--
-- Firing records here reference a run instead of a metric, so alert_firings may now
-- hold exactly one source: a metric (threshold rules) or a run (failure-window rules).
--
-- Snapshot note: the count uses the transaction's consistent read view. Two failures
-- committed in parallel by two transactions can each see only their own failure, so the
-- rule can fire one failure late under heavy concurrency. It never double-fires for the
-- same run (UNIQUE alert_id + run_id).
-- =============================================================================

ALTER TABLE alert_firings
    MODIFY COLUMN metric_id INT NULL,
    ADD COLUMN run_id INT NULL,
    ADD CONSTRAINT fk_alert_firings_run FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    ADD CONSTRAINT uq_alert_firings_alert_run UNIQUE (alert_id, run_id),
    ADD CONSTRAINT chk_alert_firings_one_source CHECK ((metric_id IS NULL) + (run_id IS NULL) = 1);

DELIMITER //

CREATE PROCEDURE sp_evaluate_failure_window(IN p_run_id INT)
BEGIN
    DECLARE v_agent_id INT;
    DECLARE v_owner_id INT;
    DECLARE v_status VARCHAR(20);

    -- Locking read: the run that just changed is always the latest committed version.
    SELECT r.agent_id, g.user_id, r.status
    INTO v_agent_id, v_owner_id, v_status
    FROM runs r
    JOIN agents g ON g.id = r.agent_id
    WHERE r.id = p_run_id
    FOR SHARE;

    IF v_status = 'failed' THEN
        INSERT INTO alert_firings (alert_id, run_id, observed_value, threshold_value, fired_at)
        SELECT
            a.id,
            p_run_id,
            (
                SELECT COUNT(*)
                FROM runs f
                JOIN agents fg ON fg.id = f.agent_id
                WHERE f.status = 'failed'
                  AND fg.user_id = v_owner_id
                  AND (a.agent_id IS NULL OR f.agent_id = a.agent_id)
                  AND COALESCE(f.completed_at, f.started_at) >= NOW() - INTERVAL a.time_window_minutes MINUTE
            ),
            a.threshold_value,
            NOW()
        FROM alerts a
        WHERE a.rule_type = 'failure_window'
          AND a.status IN ('active', 'triggered')
          AND (a.agent_id = v_agent_id OR (a.agent_id IS NULL AND a.user_id = v_owner_id))
          AND (
                SELECT COUNT(*)
                FROM runs f
                JOIN agents fg ON fg.id = f.agent_id
                WHERE f.status = 'failed'
                  AND fg.user_id = v_owner_id
                  AND (a.agent_id IS NULL OR f.agent_id = a.agent_id)
                  AND COALESCE(f.completed_at, f.started_at) >= NOW() - INTERVAL a.time_window_minutes MINUTE
              ) >= a.threshold_value;

        UPDATE alerts
        SET status = 'triggered', last_triggered_at = NOW()
        WHERE id IN (SELECT alert_id FROM alert_firings WHERE run_id = p_run_id);
    END IF;
END//

-- Fire when a run becomes failed: either created failed, or transitioned into failed.
CREATE TRIGGER trg_runs_after_insert_failure_window
AFTER INSERT ON runs
FOR EACH ROW
BEGIN
    IF NEW.status = 'failed' THEN
        CALL sp_evaluate_failure_window(NEW.id);
    END IF;
END//

CREATE TRIGGER trg_runs_after_update_failure_window
AFTER UPDATE ON runs
FOR EACH ROW
BEGIN
    IF NEW.status = 'failed' AND OLD.status <> 'failed' THEN
        CALL sp_evaluate_failure_window(NEW.id);
    END IF;
END//

DELIMITER ;
