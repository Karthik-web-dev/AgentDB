-- A rolling, bounded summary for older context. Raw messages in agent_memory are retained.
CREATE TABLE IF NOT EXISTS agent_memory_summaries (
    agent_id INT NOT NULL PRIMARY KEY,
    summary TEXT NOT NULL,
    summarized_through_id INT NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_memory_summaries_agent FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
