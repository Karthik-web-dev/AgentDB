USE agentdb;

DELIMITER //

-- 1. Run Completion Audit Trigger: Automatically records audit logs when an agent run finishes or fails
DROP TRIGGER IF EXISTS trg_runs_after_update_audit //
CREATE TRIGGER trg_runs_after_update_audit
AFTER UPDATE ON runs
FOR EACH ROW
BEGIN
    IF OLD.status != NEW.status AND NEW.status IN ('completed', 'failed') THEN
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, timestamp)
        VALUES (
            NULL,
            CONCAT('RUN_', UPPER(NEW.status)),
            'runs',
            NEW.id,
            JSON_OBJECT(
                'agent_id', NEW.agent_id,
                'task_id', NEW.task_id,
                'previous_status', OLD.status,
                'new_status', NEW.status,
                'execution_time_ms', NEW.execution_time_ms,
                'error_message', NEW.error_message
            ),
            NOW()
        );
    END IF;
END //

-- 2. Agent Configuration Change Trigger: Records audit entries when agent settings or status are modified
DROP TRIGGER IF EXISTS trg_agents_after_update_audit //
CREATE TRIGGER trg_agents_after_update_audit
AFTER UPDATE ON agents
FOR EACH ROW
BEGIN
    IF OLD.status != NEW.status OR OLD.environment != NEW.environment OR OLD.model != NEW.model THEN
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, timestamp)
        VALUES (
            NEW.user_id,
            'UPDATE_AGENT_CONFIG',
            'agents',
            NEW.id,
            JSON_OBJECT(
                'agent_name', NEW.name,
                'old_status', OLD.status,
                'new_status', NEW.status,
                'old_environment', OLD.environment,
                'new_environment', NEW.environment,
                'old_model', OLD.model,
                'new_model', NEW.model
            ),
            NOW()
        );
    END IF;
END //

DELIMITER ;
