-- =============================================================================
-- Novelty 1: Tamper-evident audit chain (database-enforced hash chain)
-- =============================================================================
-- Every audit row stores the SHA-256 of its own content together with the hash of the
-- row before it. The hash is computed by a BEFORE INSERT trigger, so no application
-- code path can insert an audit row without a valid link. Editing or deleting any row
-- breaks every later link, and sp_verify_audit_chain() reports the first broken row.
--
-- Components:
--   audit_chain_head               singleton row holding the latest sequence number and hash
--   fn_audit_row_hash()            the one hash definition, shared by the trigger and the verifier
--   trg_audit_logs_chain_*         assign chain_seq / prev_hash / row_hash on insert
--   trg_audit_logs_no_update/delete  make chained rows immutable (append-only)
--   sp_backfill_audit_chain()      chains legacy rows that existed before this migration
--   sp_verify_audit_chain()        recomputes the whole chain and reports integrity
--
-- Requirement: creating functions and triggers with binary logging enabled needs
-- log_bin_trust_function_creators=1 (or SUPER privilege). See docs/setup.md.
-- =============================================================================

-- 1. A user with audit history must not be deletable: an ON DELETE SET NULL would rewrite
--    user_id on audit rows and silently break their hashes.
ALTER TABLE audit_logs DROP FOREIGN KEY fk_audit_user;
ALTER TABLE audit_logs
    ADD CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT;

-- 2. Chain columns. Nullable so that legacy rows can be backfilled (see sp_backfill_audit_chain).
ALTER TABLE audit_logs
    ADD COLUMN chain_seq BIGINT UNSIGNED NULL,
    ADD COLUMN prev_hash CHAR(64) NULL,
    ADD COLUMN row_hash CHAR(64) NULL,
    ADD CONSTRAINT uq_audit_logs_chain_seq UNIQUE (chain_seq);

-- 3. Singleton head of the chain. The CHECK keeps it to exactly one row.
CREATE TABLE IF NOT EXISTS audit_chain_head (
    id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
    last_seq BIGINT UNSIGNED NOT NULL,
    last_hash CHAR(64) NOT NULL,
    CONSTRAINT chk_audit_chain_head_singleton CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO audit_chain_head (id, last_seq, last_hash) VALUES (1, 0, REPEAT('0', 64));

DELIMITER //

-- 4. The single hash definition. Any change here must be matched by a new migration,
--    because existing rows were hashed with the old definition.
CREATE FUNCTION fn_audit_row_hash(
    p_prev CHAR(64),
    p_seq BIGINT UNSIGNED,
    p_user_id INT,
    p_action VARCHAR(50),
    p_entity_type VARCHAR(50),
    p_entity_id INT,
    p_details TEXT,
    p_ts DATETIME
) RETURNS CHAR(64) DETERMINISTIC
BEGIN
    -- IFNULL keeps NULL fields in the hash input (CONCAT_WS would otherwise drop them).
    RETURN SHA2(
        CONCAT_WS('|',
            p_prev,
            CAST(p_seq AS CHAR),
            IFNULL(CAST(p_user_id AS CHAR), '~'),
            p_action,
            p_entity_type,
            IFNULL(CAST(p_entity_id AS CHAR), '~'),
            IFNULL(p_details, '~'),
            DATE_FORMAT(p_ts, '%Y-%m-%d %H:%i:%s')
        ),
        256
    );
END//

-- 5. Assign the next position in the chain. FOR UPDATE serialises concurrent inserts,
--    so chain order always equals lock order even under concurrency.
CREATE TRIGGER trg_audit_logs_chain_before_insert
BEFORE INSERT ON audit_logs
FOR EACH ROW
BEGIN
    DECLARE v_seq BIGINT UNSIGNED;
    DECLARE v_prev CHAR(64);

    SELECT last_seq, last_hash INTO v_seq, v_prev
    FROM audit_chain_head
    WHERE id = 1
    FOR UPDATE;

    -- Without the head row there is no position to assign. Refuse the insert instead of
    -- writing a row with a NULL chain position, which would silently escape verification.
    IF v_seq IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'audit chain head is missing: audit_chain_head must contain row id = 1';
    END IF;

    SET NEW.chain_seq = v_seq + 1;
    SET NEW.prev_hash = v_prev;
    SET NEW.row_hash = fn_audit_row_hash(
        v_prev,
        NEW.chain_seq,
        NEW.user_id,
        NEW.action,
        NEW.entity_type,
        NEW.entity_id,
        CAST(NEW.details AS CHAR),
        NEW.timestamp
    );
END//

-- 6. Advance the head to the row just written (same transaction, so a rollback undoes both).
CREATE TRIGGER trg_audit_logs_chain_after_insert
AFTER INSERT ON audit_logs
FOR EACH ROW
BEGIN
    UPDATE audit_chain_head
    SET last_seq = NEW.chain_seq, last_hash = NEW.row_hash
    WHERE id = 1;
END//

-- 7. Chained rows are immutable. Legacy rows (row_hash IS NULL) may still be updated,
--    which lets sp_backfill_audit_chain() chain them once.
CREATE TRIGGER trg_audit_logs_no_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW
BEGIN
    IF OLD.row_hash IS NOT NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'audit_logs is tamper-evident: chained rows cannot be updated';
    END IF;
END//

CREATE TRIGGER trg_audit_logs_no_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'audit_logs is append-only: rows cannot be deleted';
END//

-- 8. Chain legacy rows that were inserted before this migration. Refuses to run if any
--    row is already chained, so it cannot re-number a live chain.
CREATE PROCEDURE sp_backfill_audit_chain()
BEGIN
    DECLARE v_done INT DEFAULT 0;
    DECLARE v_id INT;
    DECLARE v_user INT;
    DECLARE v_action VARCHAR(50);
    DECLARE v_etype VARCHAR(50);
    DECLARE v_eid INT;
    DECLARE v_details TEXT;
    DECLARE v_ts DATETIME;
    DECLARE v_seq BIGINT UNSIGNED DEFAULT 0;
    DECLARE v_prev CHAR(64) DEFAULT REPEAT('0', 64);
    DECLARE v_hash CHAR(64);
    DECLARE cur CURSOR FOR
        SELECT id, user_id, action, entity_type, entity_id, CAST(details AS CHAR), timestamp
        FROM audit_logs
        WHERE row_hash IS NULL
        ORDER BY id;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    IF EXISTS (SELECT 1 FROM audit_logs WHERE row_hash IS NOT NULL) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Backfill refused: the audit chain already contains chained rows';
    END IF;

    OPEN cur;
    chain_loop: LOOP
        FETCH cur INTO v_id, v_user, v_action, v_etype, v_eid, v_details, v_ts;
        IF v_done = 1 THEN
            LEAVE chain_loop;
        END IF;
        SET v_seq = v_seq + 1;
        SET v_hash = fn_audit_row_hash(v_prev, v_seq, v_user, v_action, v_etype, v_eid, v_details, v_ts);
        UPDATE audit_logs
        SET chain_seq = v_seq, prev_hash = v_prev, row_hash = v_hash
        WHERE id = v_id;
        SET v_prev = v_hash;
    END LOOP;
    CLOSE cur;

    UPDATE audit_chain_head SET last_seq = v_seq, last_hash = v_prev WHERE id = 1;
END//

-- 9. Recompute the whole chain. Outputs:
--    p_is_valid         TRUE only if every link, every hash and the head all match
--    p_rows_checked     number of chained rows examined
--    p_first_broken_seq chain position of the first failing row (NULL when valid)
CREATE PROCEDURE sp_verify_audit_chain(
    OUT p_is_valid BOOLEAN,
    OUT p_rows_checked BIGINT,
    OUT p_first_broken_seq BIGINT
)
BEGIN
    DECLARE v_done INT DEFAULT 0;
    DECLARE v_seq BIGINT UNSIGNED;
    DECLARE v_user INT;
    DECLARE v_action VARCHAR(50);
    DECLARE v_etype VARCHAR(50);
    DECLARE v_eid INT;
    DECLARE v_details TEXT;
    DECLARE v_ts DATETIME;
    DECLARE v_prev CHAR(64);
    DECLARE v_hash CHAR(64);
    DECLARE v_expected_seq BIGINT UNSIGNED DEFAULT 1;
    DECLARE v_expected_prev CHAR(64) DEFAULT REPEAT('0', 64);
    DECLARE v_head_seq BIGINT UNSIGNED;
    DECLARE v_head_hash CHAR(64);
    DECLARE cur CURSOR FOR
        SELECT chain_seq, user_id, action, entity_type, entity_id, CAST(details AS CHAR), timestamp, prev_hash, row_hash
        FROM audit_logs
        WHERE chain_seq IS NOT NULL
        ORDER BY chain_seq;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    SET p_is_valid = TRUE;
    SET p_rows_checked = 0;
    SET p_first_broken_seq = NULL;

    OPEN cur;
    scan_loop: LOOP
        FETCH cur INTO v_seq, v_user, v_action, v_etype, v_eid, v_details, v_ts, v_prev, v_hash;
        IF v_done = 1 THEN
            LEAVE scan_loop;
        END IF;
        SET p_rows_checked = p_rows_checked + 1;

        -- A gap in chain_seq means a row was removed; a wrong prev_hash means a row was
        -- reordered or replaced; a wrong row_hash means the row's content was altered.
        IF v_seq <> v_expected_seq
           OR v_prev <> v_expected_prev
           OR v_hash <> fn_audit_row_hash(v_prev, v_seq, v_user, v_action, v_etype, v_eid, v_details, v_ts) THEN
            SET p_is_valid = FALSE;
            SET p_first_broken_seq = v_seq;
            LEAVE scan_loop;
        END IF;

        SET v_expected_seq = v_seq + 1;
        SET v_expected_prev = v_hash;
    END LOOP;
    CLOSE cur;

    -- The head must point at the last verified row. This catches a tail that was truncated
    -- by someone who bypassed the immutability triggers.
    IF p_is_valid THEN
        SELECT last_seq, last_hash INTO v_head_seq, v_head_hash FROM audit_chain_head WHERE id = 1;
        IF v_head_seq <> v_expected_seq - 1 OR v_head_hash <> v_expected_prev THEN
            SET p_is_valid = FALSE;
            SET p_first_broken_seq = v_expected_seq;
        END IF;
    END IF;
END//

DELIMITER ;
