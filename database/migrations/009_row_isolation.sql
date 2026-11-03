-- =============================================================================
-- Novelty 11: Database-enforced row isolation per user
-- =============================================================================
-- The API already checks ownership in Python. This migration adds a second, independent
-- line of defence inside MySQL: "owned" views that return only the rows of the user whose
-- id is stored in the session variable @app_user_id. A query written without a WHERE
-- clause on the owner still returns only that user's data.
--
-- The API sets @app_user_id once per request, right after it authenticates the caller.
-- If the variable is unset, fn_current_user_id() returns NULL and the views return no rows
-- (fail closed).
--
-- Components:
--   fn_current_user_id()        reads @app_user_id (NULL when unset)
--   v_owned_agents              agents owned by the current user
--   v_owned_runs                runs of the current user's agents
--   v_owned_error_signatures    error signatures of the current user
--   v_owned_alerts              alert rules of the current user
-- =============================================================================

DELIMITER //

CREATE FUNCTION fn_current_user_id() RETURNS INT
    READS SQL DATA
    NOT DETERMINISTIC
BEGIN
    -- Returns NULL when the variable is unset, so every owned view yields no rows.
    RETURN CAST(@app_user_id AS SIGNED);
END//

DELIMITER ;

CREATE OR REPLACE VIEW v_owned_agents AS
SELECT a.*
FROM agents a
WHERE a.user_id = fn_current_user_id();

CREATE OR REPLACE VIEW v_owned_runs AS
SELECT r.*
FROM runs r
JOIN agents a ON a.id = r.agent_id
WHERE a.user_id = fn_current_user_id();

CREATE OR REPLACE VIEW v_owned_error_signatures AS
SELECT s.*
FROM error_signatures s
WHERE s.user_id = fn_current_user_id();

CREATE OR REPLACE VIEW v_owned_alerts AS
SELECT al.*
FROM alerts al
WHERE al.user_id = fn_current_user_id();
