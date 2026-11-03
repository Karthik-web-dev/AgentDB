// Response shapes returned by the backend (backend/app/schemas). Keep these in step with the API.

export interface User {
  id: number
  email: string
  full_name: string
  role: string
  created_at: string
}

export interface Token {
  access_token: string
  token_type: string
}

export interface Agent {
  id: number
  user_id: number
  name: string
  description: string | null
  model: string
  environment: 'production' | 'staging' | 'development'
  status: 'active' | 'inactive' | 'maintenance'
  version: string
  created_at: string
  updated_at: string
}

export interface TaskItem {
  id: number
  agent_id: number
  title: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled'
  priority: 'low' | 'medium' | 'high' | 'critical'
  created_at: string
}

export interface RunItem {
  id: number
  agent_id: number
  task_id: number | null
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  completed_at: string | null
}

export interface LogItem {
  id: number
  run_id: number
  agent_id: number
  severity: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
  message: string
  timestamp: string
}

export interface AlertRule {
  id: number
  user_id: number
  agent_id: number | null
  rule_name: string
  rule_type: 'threshold' | 'failure_window'
  metric_name: string
  condition_operator: string
  threshold_value: number
  time_window_minutes: number
  status: 'active' | 'triggered' | 'disabled' | 'resolved'
  last_triggered_at: string | null
  created_at: string
  updated_at: string
}

export interface AlertFiring {
  id: number
  alert_id: number
  metric_id: number | null
  run_id: number | null
  observed_value: number
  threshold_value: number
  fired_at: string
}

export interface AuditRecord {
  id: number
  user_id: number | null
  action: string
  entity_type: string
  entity_id: number | null
  details: unknown
  timestamp: string
  chain_seq: number | null
  prev_hash: string | null
  row_hash: string | null
}

export interface ChainVerification {
  is_valid: boolean
  rows_checked: number
  first_broken_seq: number | null
  message: string
}

export interface LatencyAnomaly {
  run_id: number
  agent_id: number
  started_at: string
  latency_ms: number
  baseline_mean_ms: number
  baseline_stddev_ms: number | null
  baseline_size: number
  z_score: number | null
  detection_reason: 'z_score' | 'flat_baseline'
}

export interface AgentOverview {
  agent_id: number
  agent_name: string
  runs_total: number
  runs_completed: number
  runs_failed: number
  failure_rate_pct: number
  avg_latency_ms: number | null
  max_latency_ms: number | null
}

export interface AgentCost {
  agent_id: number
  agent_name: string
  total_runs: number
  priced_runs: number
  unpriced_runs: number
  runs_without_usage: number
  input_tokens: number
  output_tokens: number
  total_cost_usd: number
}

/** What the agent list endpoint returns (no description, owner or timestamps). */
export type AgentSummary = Pick<Agent, 'id' | 'name' | 'model' | 'environment' | 'status' | 'version'>

export interface MemoryTurn {
  id: number
  run_id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatResult {
  run_id: number
  model: string
  reply: string
  memory_messages_used: number
  context_original_chars: number
  context_sent_chars: number
  context_reduction_pct: number
  summary_updated: boolean
}

export interface MemorySummary {
  agent_id: number
  summary: string
  summarized_through_id: number
  source_message_count: number
  source_chars: number
  summary_chars: number
  reduction_pct: number
}
