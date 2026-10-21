-- =============================================================================
-- Novelty 8: Error signatures (normalised, de-duplicated failure messages)
-- =============================================================================
-- "Rate limit exceeded for 1200 tokens" and "Rate limit exceeded for 980 tokens" are the
-- same failure. The database normalises each error message (lower-case, digits replaced
-- by '#', whitespace collapsed), hashes the result, and groups runs by that hash per owner.
-- Each new error message therefore lands on exactly one signature, and occurrence counts
-- are maintained by the database itself.
--
-- Signatures are scoped per owner: the same text written by two users yields two separate
-- signatures, so one user's error messages never become visible to another user.
--
-- Components:
--   error_signatures                    one row per (owner, normalised message)
--   runs.error_signature_id             the signature a run's error belongs to
--   trg_runs_error_signature_insert     assigns the signature on insert
--   trg_runs_error_signature_update     reassigns it when the error message changes
-- =============================================================================

CREATE TABLE IF NOT EXISTS error_signatures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    signature_hash CHAR(64) NOT NULL,
    normalized_message TEXT NOT NULL,
    occurrences INT UNSIGNED NOT NULL DEFAULT 0,
    first_seen DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,
    CONSTRAINT fk_error_signatures_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT uq_error_signatures_user_hash UNIQUE (user_id, signature_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE runs
    ADD COLUMN error_signature_id INT NULL,
    ADD CONSTRAINT fk_runs_error_signature FOREIGN KEY (error_signature_id) REFERENCES error_signatures(id) ON DELETE RESTRICT,
    ADD INDEX idx_runs_error_signature_id (error_signature_id);

DELIMITER //

-- Shared logic: normalise, hash, and count one occurrence for the owner of the run.
-- Written as a procedure so the insert and update triggers cannot drift apart.
CREATE PROCEDURE sp_assign_error_signature(
    IN p_agent_id INT,
    IN p_error_message TEXT,
    OUT p_signature_id INT
)
BEGIN
    DECLARE v_owner_id INT;
    DECLARE v_normalized TEXT;
    DECLARE v_hash CHAR(64);

    SELECT g.user_id INTO v_owner_id FROM agents g WHERE g.id = p_agent_id;

    SET v_normalized = REGEXP_REPLACE(
        REGEXP_REPLACE(LOWER(TRIM(p_error_message)), '[[:space:]]+', ' '),
        '[0-9]+', '#'
    );
    SET v_hash = SHA2(v_normalized, 256);

    INSERT INTO error_signatures (user_id, signature_hash, normalized_message, occurrences, first_seen, last_seen)
    VALUES (v_owner_id, v_hash, v_normalized, 1, NOW(), NOW())
    ON DUPLICATE KEY UPDATE
        occurrences = occurrences + 1,
        last_seen = NOW(),
        id = LAST_INSERT_ID(id);

    SET p_signature_id = LAST_INSERT_ID();
END//

CREATE TRIGGER trg_runs_error_signature_insert
BEFORE INSERT ON runs
FOR EACH ROW
BEGIN
    DECLARE v_signature_id INT;
    IF NEW.error_message IS NOT NULL AND TRIM(NEW.error_message) <> '' THEN
        CALL sp_assign_error_signature(NEW.agent_id, NEW.error_message, v_signature_id);
        SET NEW.error_signature_id = v_signature_id;
    END IF;
END//

CREATE TRIGGER trg_runs_error_signature_update
BEFORE UPDATE ON runs
FOR EACH ROW
BEGIN
    DECLARE v_signature_id INT;
    IF NEW.error_message IS NOT NULL AND TRIM(NEW.error_message) <> ''
       AND NOT (NEW.error_message <=> OLD.error_message) THEN
        CALL sp_assign_error_signature(NEW.agent_id, NEW.error_message, v_signature_id);
        SET NEW.error_signature_id = v_signature_id;
    END IF;
END//

DELIMITER ;
