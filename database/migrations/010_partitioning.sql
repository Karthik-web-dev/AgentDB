-- =============================================================================
-- Novelty 9: Monthly partitioning of logs and events, with retention by partition drop
-- =============================================================================
-- logs and events grow fastest. They are partitioned by month on their timestamp, so:
--   * queries for a time range read only the partitions that overlap it (partition pruning)
--   * retention removes whole months with ALTER TABLE ... DROP PARTITION, which is a
--     metadata operation, far cheaper than DELETE and the only sanctioned way to age out
--     history. Row-level DELETE stays blocked by the append-only triggers (migration 004).
--
-- Trade-off (documented on purpose): MySQL does not allow foreign keys on partitioned
-- InnoDB tables. Referential integrity for these two tables is therefore enforced by
-- BEFORE INSERT triggers, which also check that logs.agent_id matches its run's agent.
--
-- Partition layout:
--   p_past            everything before 2026-01-01
--   p2026_01 .. p2026_12   one partition per month
--   p_future          everything later; sp_maintain_partitions() splits it monthly
--
-- Components:
--   trg_logs_integrity_before_insert, trg_events_integrity_before_insert
--   sp_ensure_month_partition(table, month)   creates a month partition if missing
--   sp_maintain_partitions()                 keeps the next 3 months ready; run daily by an EVENT
--   sp_drop_partitions_before(table, cutoff) retention: drops whole partitions older than cutoff
--   ev_partition_maintenance                 scheduled EVENT (requires event_scheduler = ON)
-- =============================================================================

-- 1. Foreign keys cannot survive partitioning; the triggers below replace them.
ALTER TABLE logs DROP FOREIGN KEY fk_logs_run, DROP FOREIGN KEY fk_logs_agent;
ALTER TABLE events DROP FOREIGN KEY fk_events_run;

DELIMITER //

CREATE TRIGGER trg_logs_integrity_before_insert
BEFORE INSERT ON logs
FOR EACH ROW
BEGIN
    DECLARE v_matches INT DEFAULT 0;
    DECLARE v_run_agent INT;

    SELECT COUNT(*), MAX(agent_id) INTO v_matches, v_run_agent
    FROM runs WHERE id = NEW.run_id;

    IF v_matches = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'logs.run_id does not reference an existing run';
    END IF;
    IF v_run_agent <> NEW.agent_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'logs.agent_id must match the agent of its run';
    END IF;
END//

CREATE TRIGGER trg_events_integrity_before_insert
BEFORE INSERT ON events
FOR EACH ROW
BEGIN
    DECLARE v_matches INT DEFAULT 0;

    SELECT COUNT(*) INTO v_matches FROM runs WHERE id = NEW.run_id;
    IF v_matches = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'events.run_id does not reference an existing run';
    END IF;
END//

-- Partition names are built from a fixed whitelist, never from caller text.
CREATE PROCEDURE sp_ensure_month_partition(IN p_table VARCHAR(64), IN p_month DATE)
BEGIN
    DECLARE v_name VARCHAR(64);
    DECLARE v_bound INT;
    DECLARE v_exists INT DEFAULT 0;
    DECLARE v_ddl TEXT;

    IF p_table NOT IN ('logs', 'events') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'partition maintenance is limited to logs and events';
    END IF;

    SET v_name = CONCAT('p', DATE_FORMAT(p_month, '%Y%m'));
    SET v_bound = TO_DAYS(DATE_ADD(DATE_FORMAT(p_month, '%Y-%m-01'), INTERVAL 1 MONTH));

    SELECT COUNT(*) INTO v_exists
    FROM information_schema.partitions
    WHERE table_schema = DATABASE() AND table_name = p_table AND partition_name = v_name;

    IF v_exists = 0 THEN
        SET v_ddl = CONCAT(
            'ALTER TABLE `', p_table, '` REORGANIZE PARTITION p_future INTO (',
            'PARTITION ', v_name, ' VALUES LESS THAN (', v_bound, '),',
            'PARTITION p_future VALUES LESS THAN MAXVALUE)'
        );
        SET @ddl_stmt = v_ddl;
        PREPARE stmt FROM @ddl_stmt;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END//

CREATE PROCEDURE sp_maintain_partitions()
BEGIN
    DECLARE v_offset INT DEFAULT 0;
    WHILE v_offset <= 2 DO
        CALL sp_ensure_month_partition('logs', DATE_ADD(CURDATE(), INTERVAL v_offset MONTH));
        CALL sp_ensure_month_partition('events', DATE_ADD(CURDATE(), INTERVAL v_offset MONTH));
        SET v_offset = v_offset + 1;
    END WHILE;
END//

-- Retention: drop every partition whose upper bound is on or before the cutoff date.
-- Rows in dropped partitions are removed without firing triggers, by design (see header).
CREATE PROCEDURE sp_drop_partitions_before(IN p_table VARCHAR(64), IN p_cutoff DATE, OUT p_dropped INT)
BEGIN
    DECLARE v_done INT DEFAULT 0;
    DECLARE v_name VARCHAR(64);
    DECLARE v_bound VARCHAR(64);
    DECLARE v_cutoff_days INT;
    DECLARE cur CURSOR FOR
        SELECT partition_name, partition_description
        FROM tmp_partition_list
        ORDER BY partition_ordinal_position;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    IF p_table NOT IN ('logs', 'events') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'retention is limited to logs and events';
    END IF;

    SET p_dropped = 0;
    SET v_cutoff_days = TO_DAYS(p_cutoff);

    DROP TEMPORARY TABLE IF EXISTS tmp_partition_list;
    CREATE TEMPORARY TABLE tmp_partition_list AS
    SELECT partition_name, partition_description, partition_ordinal_position
    FROM information_schema.partitions
    WHERE table_schema = DATABASE()
      AND table_name = p_table
      AND partition_name <> 'p_future';

    OPEN cur;
    drop_loop: LOOP
        FETCH cur INTO v_name, v_bound;
        IF v_done = 1 THEN
            LEAVE drop_loop;
        END IF;
        IF CAST(v_bound AS UNSIGNED) <= v_cutoff_days THEN
            SET @ddl_stmt = CONCAT('ALTER TABLE `', p_table, '` DROP PARTITION `', v_name, '`');
            PREPARE stmt FROM @ddl_stmt;
            EXECUTE stmt;
            DEALLOCATE PREPARE stmt;
            SET p_dropped = p_dropped + 1;
        END IF;
    END LOOP;
    CLOSE cur;

    DROP TEMPORARY TABLE IF EXISTS tmp_partition_list;
END//

DELIMITER ;

-- 2. Partition the tables. The primary key must include the partition column.
ALTER TABLE logs
    DROP PRIMARY KEY,
    ADD PRIMARY KEY (id, timestamp);

ALTER TABLE logs
    PARTITION BY RANGE (TO_DAYS(timestamp)) (
        PARTITION p_past VALUES LESS THAN (TO_DAYS('2026-01-01')),
        PARTITION p_future VALUES LESS THAN MAXVALUE
    );

ALTER TABLE events
    DROP PRIMARY KEY,
    ADD PRIMARY KEY (id, timestamp);

ALTER TABLE events
    PARTITION BY RANGE (TO_DAYS(timestamp)) (
        PARTITION p_past VALUES LESS THAN (TO_DAYS('2026-01-01')),
        PARTITION p_future VALUES LESS THAN MAXVALUE
    );

-- 3. Create the 2026 month partitions up front (sequential: each split uses p_future).
CALL sp_ensure_month_partition('logs', '2026-01-01');
CALL sp_ensure_month_partition('logs', '2026-02-01');
CALL sp_ensure_month_partition('logs', '2026-03-01');
CALL sp_ensure_month_partition('logs', '2026-04-01');
CALL sp_ensure_month_partition('logs', '2026-05-01');
CALL sp_ensure_month_partition('logs', '2026-06-01');
CALL sp_ensure_month_partition('logs', '2026-07-01');
CALL sp_ensure_month_partition('logs', '2026-08-01');
CALL sp_ensure_month_partition('logs', '2026-09-01');
CALL sp_ensure_month_partition('logs', '2026-10-01');
CALL sp_ensure_month_partition('logs', '2026-11-01');
CALL sp_ensure_month_partition('logs', '2026-12-01');

CALL sp_ensure_month_partition('events', '2026-01-01');
CALL sp_ensure_month_partition('events', '2026-02-01');
CALL sp_ensure_month_partition('events', '2026-03-01');
CALL sp_ensure_month_partition('events', '2026-04-01');
CALL sp_ensure_month_partition('events', '2026-05-01');
CALL sp_ensure_month_partition('events', '2026-06-01');
CALL sp_ensure_month_partition('events', '2026-07-01');
CALL sp_ensure_month_partition('events', '2026-08-01');
CALL sp_ensure_month_partition('events', '2026-09-01');
CALL sp_ensure_month_partition('events', '2026-10-01');
CALL sp_ensure_month_partition('events', '2026-11-01');
CALL sp_ensure_month_partition('events', '2026-12-01');

-- 4. Keep the next months ready. Requires event_scheduler = ON (see docs/setup.md).
CREATE EVENT ev_partition_maintenance
    ON SCHEDULE EVERY 1 DAY
    STARTS '2026-01-01 02:00:00'
    DO CALL sp_maintain_partitions();
