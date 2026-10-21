# AgentDB novelties

File paths in the table are relative to `database/` (for example `migrations/001_audit_hash_chain.sql`
means `database/migrations/001_audit_hash_chain.sql`).

Twelve database-centred features. Each one is enforced by MySQL (triggers, stored procedures,
views, events or constraints) rather than only by application code, and each has tests that
run against a real MySQL 8 server.

| # | Feature | Where it lives | Enforced by | Tests |
|---|---------|----------------|-------------|-------|
| 1 | Tamper-evident audit chain | `migrations/001_audit_hash_chain.sql` | `BEFORE INSERT` trigger computes SHA-256 links; `BEFORE UPDATE/DELETE` guards; `sp_verify_audit_chain` | `test_audit_chain.py` |
| 2 | Append-only history | `migrations/004_append_only.sql` | `BEFORE UPDATE/DELETE` triggers on events, logs, metrics; `BEFORE DELETE` on runs | `test_append_only.py` |
| 3 | In-database alert engine | `migrations/002_alert_engine.sql` | `AFTER INSERT` trigger on metrics calls `sp_evaluate_metric_alerts` | `test_alert_engine.py` |
| 4 | Sliding-window failure rules | `migrations/005_failure_window.sql` | `AFTER INSERT/UPDATE` triggers on runs call `sp_evaluate_failure_window` | `test_failure_window.py` |
| 5 | Latency anomaly detection | `migrations/003_latency_anomaly.sql` | Window functions over the previous 20 runs per agent; `sp_detect_latency_anomalies` | `test_latency_anomaly.py` |
| 6 | Cost attribution with method | `migrations/006_cost_attribution.sql` | `v_run_cost` view; price history by effective date; token guard trigger | `test_cost_attribution.py` |
| 7 | Multi-agent trace trees | `migrations/007_trace_tree.sql` | Self-referencing `parent_run_id`; same-owner and immutability triggers; recursive CTEs | `test_trace_tree.py` |
| 8 | Error signatures | `migrations/008_error_signatures.sql` | Normalisation and hashing inside `sp_assign_error_signature`, called from insert/update triggers | `test_error_signatures.py` |
| 9 | Monthly partitioning and retention | `migrations/010_partitioning.sql` | `RANGE` partitions on `timestamp`; integrity triggers replace foreign keys; `sp_drop_partitions_before` | `test_partitioning.py` |
| 10 | Incremental hourly rollups | `migrations/011_hourly_rollups.sql` | `sp_refresh_hourly_stats` (idempotent); scheduled `EVENT`; refresh-on-read in the overview endpoint | `test_hourly_rollups.py` |
| 11 | Database-enforced row isolation | `migrations/009_row_isolation.sql` | `fn_current_user_id()` reads a per-transaction identity; `v_owned_*` views | `test_row_isolation.py` |
| 12 | Plan-verified queries | `tests/test_query_plans.py` | `EXPLAIN` assertions on the index or partition each critical query must use | `test_query_plans.py` |

## Design decisions worth knowing

- **Foreign keys were replaced on partitioned tables (novelty 9).** MySQL does not allow
  foreign keys on partitioned InnoDB tables, so `logs` and `events` use `BEFORE INSERT`
  triggers to check that their run exists, and that `logs.agent_id` matches the run's agent.
- **Retention is partition-based (novelty 9).** Deleting rows is forbidden (novelty 2).
  Old months leave the database by dropping their partition, which does not fire triggers.
  That is the only sanctioned removal of history.
- **Identity is carried per transaction (novelty 11).** `@app_user_id` is a connection
  variable, so it is cleared when a connection leaves the pool and re-applied at the start of
  every transaction. The regression tests in `test_row_isolation.py` cover both cases.
- **Counts use locking reads or one consistent snapshot.** The alert and failure-window
  procedures read the metric or run with `FOR SHARE`, so a long transaction cannot make the
  engine miss a row. The failure-window count uses the transaction's snapshot, so under heavy
  parallel failures it can fire one failure late. It never fires twice for the same run.

## Known limits

- Novelty 1 proves that stored rows were not altered after they were written, but it cannot
  prove that every action was recorded. A user with direct database administrator rights can
  still drop the triggers, and the verifier would then report the changes.
- Novelty 10 rollups lag by up to the event interval (one hour) unless a caller refreshes the
  range it needs. The overview endpoint always refreshes the range it reads.
- Novelty 5 ignores agents with fewer than 5 prior completed runs, because a z-score from so
  few samples is not meaningful.
- Cost figures depend on prices entered into `model_pricing`. No prices ship with the project,
  so the cost of a run is reported as `unpriced` until a price is added.
