-- =============================================================================
-- Novelty 3: In-database alert engine
-- =============================================================================
-- Every new metric row is evaluated against the owner's active alert rules inside MySQL,
-- in the same transaction that stores the metric. No application process has to poll,
-- so an alert cannot be missed because a worker was down, and every firing is recorded
-- with the value and the threshold that were in force at that moment.
--
-- Scope rules (enforced here, not in the API):
--   * a rule with agent_id set applies to that agent only
--   * a rule with agent_id NULL ("global") applies to every agent owned by the rule's user
--   * a global rule never fires on another user's agent
--
-- Components:
--   alert_firings                 append-only history of every rule firing
--   sp_evaluate_metric_alerts()   evaluates all matching rules for one metric row
--   trg_metrics_after_insert_alerts   calls the procedure for every new metric
-- =============================================================================

-- Rule kinds. 'threshold' rules compare one metric value (this migration).
-- 'failure_window' rules count failed runs in a sliding window (migration 005).
ALTER TABLE alerts
    ADD COLUMN rule_type VARCHAR(20) NOT NULL DEFAULT 'threshold',
    ADD CONSTRAINT chk_alerts_rule_type CHECK (rule_type IN ('threshold', 'failure_window'));

CREATE TABLE IF NOT EXISTS alert_firings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    alert_id INT NOT NULL,
    metric_id INT NOT NULL,
    observed_value DOUBLE NOT NULL,
    threshold_value DOUBLE NOT NULL,   -- snapshot of the rule's threshold when it fired
    fired_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert_firings_alert FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE,
    CONSTRAINT fk_alert_firings_metric FOREIGN KEY (metric_id) REFERENCES metrics(id) ON DELETE CASCADE,
    CONSTRAINT uq_alert_firings_alert_metric UNIQUE (alert_id, metric_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Supports "recent firings" listings and time-window reports.
CREATE INDEX idx_alert_firings_fired_at ON alert_firings(fired_at);

DELIMITER //

CREATE PROCEDURE sp_evaluate_metric_alerts(IN p_metric_id INT)
BEGIN
    DECLARE v_metric_name VARCHAR(50);
    DECLARE v_value DOUBLE;
    DECLARE v_agent_id INT;
    DECLARE v_owner_id INT;

    -- FOR SHARE is a locking read: it sees the latest committed rows, not the caller's
    -- snapshot. A long-running transaction therefore cannot make the engine miss a metric.
    SELECT m.metric_name, m.metric_value, r.agent_id, g.user_id
    INTO v_metric_name, v_value, v_agent_id, v_owner_id
    FROM metrics m
    JOIN runs r ON r.id = m.run_id
    JOIN agents g ON g.id = r.agent_id
    WHERE m.id = p_metric_id
    FOR SHARE;

    -- The metric's run and agent are foreign-key parents, so this cannot happen unless the
    -- schema is damaged. Fail loudly rather than silently skipping evaluation.
    IF v_agent_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Alert engine: metric has no resolvable run or agent';
    END IF;

    -- Record a firing for every rule whose scope and condition match this metric.
    INSERT INTO alert_firings (alert_id, metric_id, observed_value, threshold_value, fired_at)
    SELECT a.id, p_metric_id, v_value, a.threshold_value, NOW()
    FROM alerts a
    WHERE a.status IN ('active', 'triggered')
      AND a.rule_type = 'threshold'
      AND a.metric_name = v_metric_name
      AND (a.agent_id = v_agent_id OR (a.agent_id IS NULL AND a.user_id = v_owner_id))
      AND (
            (a.condition_operator = '>'  AND v_value >  a.threshold_value) OR
            (a.condition_operator = '>=' AND v_value >= a.threshold_value) OR
            (a.condition_operator = '<'  AND v_value <  a.threshold_value) OR
            (a.condition_operator = '<=' AND v_value <= a.threshold_value) OR
            (a.condition_operator = '==' AND v_value =  a.threshold_value) OR
            (a.condition_operator = '!=' AND v_value <> a.threshold_value)
          );

    -- Any rule that fired is now in the triggered state until it is resolved.
    UPDATE alerts
    SET status = 'triggered', last_triggered_at = NOW()
    WHERE id IN (SELECT alert_id FROM alert_firings WHERE metric_id = p_metric_id);
END//

CREATE TRIGGER trg_metrics_after_insert_alerts
AFTER INSERT ON metrics
FOR EACH ROW
BEGIN
    CALL sp_evaluate_metric_alerts(NEW.id);
END//

DELIMITER ;
