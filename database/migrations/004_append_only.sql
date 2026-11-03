-- =============================================================================
-- Novelty 2: Append-only observability history
-- =============================================================================
-- Events, logs and metrics are facts about what happened. Once written they must never
-- change, and a run's history must never disappear. The rules live in the database, so
-- they hold for every client (API, scripts, DBA sessions), not only for the Python code.
--
--   events, logs, metrics : UPDATE and DELETE are rejected
--   runs                  : DELETE is rejected (status may still change; a run is closed
--                           by setting status, not by deleting it)
--
-- Note: MySQL does not fire triggers for foreign-key cascades. The run guard below is
-- what stops a DELETE on runs from silently removing its events, logs and metrics.
-- =============================================================================

DELIMITER //

CREATE TRIGGER trg_events_no_update
BEFORE UPDATE ON events
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'events are append-only: UPDATE is not allowed';
END//

CREATE TRIGGER trg_events_no_delete
BEFORE DELETE ON events
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'events are append-only: DELETE is not allowed';
END//

CREATE TRIGGER trg_logs_no_update
BEFORE UPDATE ON logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'logs are append-only: UPDATE is not allowed';
END//

CREATE TRIGGER trg_logs_no_delete
BEFORE DELETE ON logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'logs are append-only: DELETE is not allowed';
END//

CREATE TRIGGER trg_metrics_no_update
BEFORE UPDATE ON metrics
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'metrics are append-only: UPDATE is not allowed';
END//

CREATE TRIGGER trg_metrics_no_delete
BEFORE DELETE ON metrics
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'metrics are append-only: DELETE is not allowed';
END//

CREATE TRIGGER trg_runs_no_delete
BEFORE DELETE ON runs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'runs are historical: DELETE is not allowed; set status instead';
END//

DELIMITER ;
