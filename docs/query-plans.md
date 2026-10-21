# Query plans (novelty 12)

These plans were captured with `EXPLAIN` on MySQL 8.0.46 against a database holding 3,008 runs,
30,008 logs and 307 events spread over August to October 2026, after `ANALYZE TABLE`. The test
suite (`backend/tests/test_query_plans.py`) asserts the key facts below on every run, so a schema
change that breaks one of these plans fails the build.

## 1. Log search by severity and time range

```sql
EXPLAIN SELECT id, run_id, message FROM logs
WHERE severity = 'ERROR' AND timestamp >= '2026-09-05' AND timestamp < '2026-09-10';
```

```text
table  partitions  type   key                            rows  Extra
logs   p202609     range  idx_logs_severity_timestamp    320   Using index condition
```

**Reading it:** the composite index `(severity, timestamp)` is chosen over `(timestamp)`, because
equality on severity narrows the range before the time filter. Only the `p202609` partition is
read: partition pruning from novelty 9.

## 2. Time-range scan (partition pruning)

```sql
EXPLAIN SELECT COUNT(*) FROM logs
WHERE timestamp >= '2026-09-05' AND timestamp < '2026-09-06';
```

```text
table  partitions  type   key                rows  Extra
logs   p202609     range  idx_logs_timestamp  320   Using where; Using index
```

**Reading it:** the query touches one of the twelve monthly partitions. The count is answered from
the index alone (`Using index`). For a one-day window in a large history, this is the difference
between reading one month and reading years.

## 3. Events of one run: a trade-off

```sql
EXPLAIN SELECT id FROM events WHERE run_id = 10;
```

```text
table   partitions                                                                          type  key               rows
events  p_past,p202601,...,p202612,p_future                                                 ref   idx_events_run_id  1
```

**Reading it:** the index on `run_id` is used, and it returns one row. But the predicate has no
timestamp, so MySQL must probe the index in **all 14 partitions**. This is a genuine cost of
partitioning by time. It is acceptable here because a run's events are usually read together with
the run, and the run itself is found through its primary key. If this lookup became hot, the
options are a covering index that includes `timestamp`, or a query that also carries the run's
start time so pruning can apply.

## 4. Hourly rollup range

```sql
EXPLAIN SELECT * FROM agent_hourly_stats
WHERE agent_id = 1 AND bucket_start >= '2026-08-20 00:00:00';
```

```text
table               type   key      rows  Extra
agent_hourly_stats  range  PRIMARY  600   Using where
```

**Reading it:** the composite primary key `(agent_id, bucket_start)` serves the dashboard's query
directly. No separate index is needed, and the overview endpoint's cost grows with the number of
hours requested, not with the number of runs.

## 5. Failed runs for one agent

```sql
EXPLAIN SELECT COUNT(*) FROM runs WHERE agent_id = 2 AND status = 'failed';
```

```text
table  type  key                          rows  Extra
runs   ref   idx_runs_agent_id_status     2     Using index
```

**Reading it:** the composite index `(agent_id, status)` answers the query from the index alone.
