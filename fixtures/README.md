# AIContext eval fixtures

Synthetic `AIContext` payloads (schema v1) for ganymede-brain contract tests and offline eval. Each file is one chaos scenario (or a clean steady session) built via `ganymede/scripts/gen_aicontext_fixtures.go` and `api.BuildAIContext`.

Regenerate after schema or ledger changes:

```powershell
cd ganymede
go run scripts/gen_aicontext_fixtures.go
```

## Fixture labels

Ground-truth for eval: the **primary root-cause rule** the brain should cite for *why* the session degraded, the **authored mechanism** whose precondition should match, and the **config cause** (design choice that made the failure mode possible).

| File | Chaos scenario | Primary rule | Mechanism | Config cause |
|------|----------------|--------------|-----------|--------------|
| `clean.json` | — | *(none — negative case)* | *(none)* | `cacheStrategy: cache-aside`, `replicationMode: async`, `readConsistency: replica` — steady session, no fired rules |
| `pod_kill.json` | `pod_kill` | `pod_restart` | `pod_restart_runtime` | Runtime failure (no config precondition) |
| `cache_flush.json` | `cache_flush` | `cascade_cache_db` | `cascade_cache_db_fallthrough` | `cacheStrategy: cache-aside` — flush forces DB fallthrough |
| `stall_replica.json` | `stall_replica` | `replica_cannot_catch_up` | `replica_cannot_catch_up` | `readReplicas: 2`, `replicationMode: async` |
| `split_primary_replica.json` | `split_primary_replica` | `partition_stale_reads` | `partition_stale_reads_async` | `replicationMode: async`, `readConsistency: replica` |
| `split_app_store.json` | `split_app_store` | `cache_db_stale` | `cache_db_stale_proxy` | `cacheStrategy: write-through` — cache/DB divergence under partition |
| `promote_replica.json` | `promote_replica` | `failover_write_loss` | `async_promote_write_loss` | `replicationMode: async` |
| `promote_lagging_replica.json` | `promote_lagging_replica` | `failover_write_loss` | `async_promote_write_loss` | `replicationMode: async` (lagging standby promoted) |
| `kill_replica.json` | `kill_replica` | `replica_cannot_catch_up` | `replica_cannot_catch_up` | `readReplicas: 2`, `replicationMode: async` |

### Secondary signals

Some fixtures include precursor threshold events that are not the root cause:

- **`cache_flush.json`** also fires `cache_hit_low` before `cascade_cache_db`.
- **`promote_lagging_replica.json`** and **`promote_replica.json`** share the same mechanism; the lagging variant documents `bytesLost` in event detail.

## Eval expectations

- **Negative case:** `clean.json` — brain should abstain or describe steady state; no invented rule citations.
- **Positive cases:** cite the primary rule and at least one config fact matching the config cause column.
- **Ablation (PR-22):** withhold the mechanism row from context; recovery of `triggerRules` + `precondition` is pass/fail.
