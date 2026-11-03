-- Conversation turns retained per agent and included in later OpenRouter requests.
CREATE TABLE IF NOT EXISTS agent_memory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_id INT NOT NULL,
    run_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_memory_agent FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE RESTRICT,
    CONSTRAINT fk_agent_memory_run FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE RESTRICT,
    CONSTRAINT chk_agent_memory_role CHECK (role IN ('user', 'assistant')),
    INDEX idx_agent_memory_history (agent_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
