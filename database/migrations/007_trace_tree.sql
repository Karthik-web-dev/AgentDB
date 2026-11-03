-- =============================================================================
-- Novelty 7: Multi-agent trace trees (self-referencing runs) and subtree cost roll-up
-- =============================================================================
-- A run may name a parent run, so a coordinating agent can record the sub-runs it started.
-- The tree is stored as an adjacency list (parent_run_id) and read with a recursive CTE.
--
-- Integrity rules (enforced by MySQL, not only by the API):
--   * parent_run_id must reference an existing run (foreign key)
--   * a parent must belong to the same owner as the child (trigger)
--   * parent_run_id is immutable once set (trigger). Because a parent must already exist
--     when its child is inserted, the graph can never contain a cycle.
--
-- Components:
--   runs.parent_run_id                 adjacency-list link
--   trg_runs_parent_owner_check        same-owner guard on insert
--   trg_runs_parent_immutable          blocks changing the parent after creation
--   sp_run_trace()                     the whole tree below one run, in depth-first order
--   sp_run_subtree_cost()              cost of a run plus all of its descendants
-- =============================================================================

ALTER TABLE runs
    ADD COLUMN parent_run_id INT NULL,
    ADD CONSTRAINT fk_runs_parent FOREIGN KEY (parent_run_id) REFERENCES runs(id) ON DELETE RESTRICT,
    ADD INDEX idx_runs_parent_run_id (parent_run_id);

DELIMITER //

CREATE TRIGGER trg_runs_parent_owner_check
BEFORE INSERT ON runs
FOR EACH ROW
BEGIN
    DECLARE v_child_owner INT;
    DECLARE v_parent_owner INT;

    IF NEW.parent_run_id IS NOT NULL THEN
        SELECT g.user_id INTO v_child_owner FROM agents g WHERE g.id = NEW.agent_id;
        SELECT g.user_id INTO v_parent_owner
        FROM runs p JOIN agents g ON g.id = p.agent_id
        WHERE p.id = NEW.parent_run_id
        FOR SHARE;

        IF v_parent_owner IS NULL OR v_parent_owner <> v_child_owner THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'parent run must exist and belong to the same owner';
        END IF;
    END IF;
END//

CREATE TRIGGER trg_runs_parent_immutable
BEFORE UPDATE ON runs
FOR EACH ROW
BEGIN
    IF NOT (NEW.parent_run_id <=> OLD.parent_run_id) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'parent_run_id is immutable once a run is created';
    END IF;
END//

-- Depth-first listing of the tree below p_run_id. Ownership is checked in the anchor
-- member, so a run that belongs to someone else yields an empty tree.
CREATE PROCEDURE sp_run_trace(IN p_user_id INT, IN p_run_id INT)
BEGIN
    WITH RECURSIVE tree AS (
        SELECT
            r.id AS run_id,
            r.parent_run_id,
            r.agent_id,
            r.status,
            r.started_at,
            r.execution_time_ms,
            0 AS depth,
            CAST(LPAD(r.id, 10, '0') AS CHAR(2000)) AS path
        FROM runs r
        JOIN agents g ON g.id = r.agent_id
        WHERE r.id = p_run_id
          AND g.user_id = p_user_id
        UNION ALL
        SELECT
            c.id,
            c.parent_run_id,
            c.agent_id,
            c.status,
            c.started_at,
            c.execution_time_ms,
            t.depth + 1,
            CONCAT(t.path, '>', LPAD(c.id, 10, '0'))
        FROM runs c
        JOIN tree t ON c.parent_run_id = t.run_id
        WHERE t.depth < 50  -- defensive bound; the immutable parent rule already prevents cycles
    )
    SELECT run_id, parent_run_id, agent_id, status, started_at, execution_time_ms, depth
    FROM tree
    ORDER BY path;
END//

-- Subtree cost roll-up: the run's own cost plus every descendant's cost, using the
-- per-run attribution from v_run_cost. Runs without a price are counted, not guessed.
CREATE PROCEDURE sp_run_subtree_cost(IN p_user_id INT, IN p_run_id INT)
BEGIN
    WITH RECURSIVE tree AS (
        SELECT r.id AS run_id
        FROM runs r
        JOIN agents g ON g.id = r.agent_id
        WHERE r.id = p_run_id AND g.user_id = p_user_id
        UNION ALL
        SELECT c.id
        FROM runs c
        JOIN tree t ON c.parent_run_id = t.run_id
    )
    SELECT
        p_run_id AS run_id,
        COUNT(*) AS runs_in_tree,
        SUM(CASE WHEN c.attribution_method = 'unpriced' THEN 1 ELSE 0 END) AS unpriced_runs,
        ROUND(COALESCE(SUM(c.cost_usd), 0), 6) AS subtree_cost_usd,
        'rollup' AS attribution_method
    FROM tree t
    JOIN v_run_cost c ON c.run_id = t.run_id
    -- Without this, an aggregate over an empty tree still returns one row, which would
    -- reveal that a run exists even when the caller does not own it.
    HAVING COUNT(*) > 0;
END//

DELIMITER ;
