-- =============================================================================
-- Novelty 6: Token usage and cost attribution per run, with an explicit method
-- =============================================================================
-- Agents report token usage as metrics:
--   metric_name = 'input_tokens'  or  'output_tokens',  unit = 'tokens'
-- Each row is the usage of one model call, so a run's usage is the sum of its rows.
--
-- Prices are stored per model with an effective date, and a run is priced with the price
-- that was in force when the run started. Changing a price never rewrites past costs.
--
-- Attribution method (recorded on every row, so reports can explain their totals):
--   direct    the run has token usage and a price exists for its model
--   unpriced  the run has token usage but no price exists for its model (cost is NULL)
--   no_usage  the run reported no token usage (cost is NULL)
--
-- Components:
--   model_pricing                 price history per model
--   trg_metrics_token_guard       rejects negative or fractional token counts
--   v_run_token_usage             per-run token totals
--   v_run_cost                    per-run cost with attribution method
--   sp_agent_cost_report()        per-agent totals for one owner and a time range
--   sp_run_cost_breakdown()       per-run rows for one owner and a time range
-- =============================================================================

CREATE TABLE IF NOT EXISTS model_pricing (
    model VARCHAR(50) NOT NULL,
    effective_from DATE NOT NULL,
    input_usd_per_1k DECIMAL(12, 6) NOT NULL,
    output_usd_per_1k DECIMAL(12, 6) NOT NULL,
    PRIMARY KEY (model, effective_from),
    CONSTRAINT chk_model_pricing_nonnegative CHECK (input_usd_per_1k >= 0 AND output_usd_per_1k >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DELIMITER //

CREATE TRIGGER trg_metrics_token_guard
BEFORE INSERT ON metrics
FOR EACH ROW
BEGIN
    IF NEW.metric_name IN ('input_tokens', 'output_tokens') THEN
        IF NEW.metric_value < 0 OR NEW.metric_value <> FLOOR(NEW.metric_value) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'token metrics must be non-negative whole numbers';
        END IF;
    END IF;
END//

DELIMITER ;

CREATE OR REPLACE VIEW v_run_token_usage AS
SELECT
    m.run_id,
    SUM(CASE WHEN m.metric_name = 'input_tokens' THEN m.metric_value ELSE 0 END) AS input_tokens,
    SUM(CASE WHEN m.metric_name = 'output_tokens' THEN m.metric_value ELSE 0 END) AS output_tokens
FROM metrics m
WHERE m.metric_name IN ('input_tokens', 'output_tokens')
GROUP BY m.run_id;

CREATE OR REPLACE VIEW v_run_cost AS
SELECT
    r.id AS run_id,
    r.agent_id,
    g.user_id,
    g.model,
    r.started_at,
    COALESCE(u.input_tokens, 0) AS input_tokens,
    COALESCE(u.output_tokens, 0) AS output_tokens,
    p.input_usd_per_1k,
    p.output_usd_per_1k,
    CASE
        WHEN u.run_id IS NULL THEN 'no_usage'
        WHEN p.model IS NULL THEN 'unpriced'
        ELSE 'direct'
    END AS attribution_method,
    CASE
        WHEN u.run_id IS NULL OR p.model IS NULL THEN NULL
        ELSE ROUND(
            u.input_tokens / 1000 * p.input_usd_per_1k
            + u.output_tokens / 1000 * p.output_usd_per_1k,
            6
        )
    END AS cost_usd
FROM runs r
JOIN agents g ON g.id = r.agent_id
LEFT JOIN v_run_token_usage u ON u.run_id = r.id
LEFT JOIN model_pricing p
    ON p.model = g.model
   AND p.effective_from = (
        SELECT MAX(mp.effective_from)
        FROM model_pricing mp
        WHERE mp.model = g.model
          AND mp.effective_from <= DATE(r.started_at)
   );

DELIMITER //

CREATE PROCEDURE sp_agent_cost_report(
    IN p_user_id INT,
    IN p_since DATETIME,
    IN p_until DATETIME
)
BEGIN
    SELECT
        c.agent_id,
        g.name AS agent_name,
        COUNT(*) AS total_runs,
        SUM(c.attribution_method = 'direct') AS priced_runs,
        SUM(c.attribution_method = 'unpriced') AS unpriced_runs,
        SUM(c.attribution_method = 'no_usage') AS runs_without_usage,
        SUM(c.input_tokens) AS input_tokens,
        SUM(c.output_tokens) AS output_tokens,
        ROUND(COALESCE(SUM(c.cost_usd), 0), 6) AS total_cost_usd
    FROM v_run_cost c
    JOIN agents g ON g.id = c.agent_id
    WHERE c.user_id = p_user_id
      AND c.started_at >= p_since
      AND c.started_at < p_until
    GROUP BY c.agent_id, g.name
    ORDER BY total_cost_usd DESC, c.agent_id;
END//

CREATE PROCEDURE sp_run_cost_breakdown(
    IN p_user_id INT,
    IN p_agent_id INT,
    IN p_since DATETIME,
    IN p_until DATETIME
)
BEGIN
    SELECT
        c.run_id,
        c.agent_id,
        c.started_at,
        c.input_tokens,
        c.output_tokens,
        c.cost_usd,
        c.attribution_method
    FROM v_run_cost c
    WHERE c.user_id = p_user_id
      AND (p_agent_id IS NULL OR c.agent_id = p_agent_id)
      AND c.started_at >= p_since
      AND c.started_at < p_until
    ORDER BY c.started_at DESC, c.run_id DESC;
END//

DELIMITER ;
