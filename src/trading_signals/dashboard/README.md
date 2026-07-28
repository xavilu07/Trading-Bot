# Dashboard read model

SQLite is a rebuildable projection, never a canonical producer dependency.
Operational code writes the original files; the finite dashboard projector
only reads them and writes a separately configured `.sqlite` target.

## Sources projected in v1

- `scheduler_heartbeat` → `system_snapshots`
- `scan_runs` → `cycles`
- `trade_signals` → `signals`

The remaining logical sources stay in `source_metadata` with their observed
availability but are not ingested in this phase. JSONL and CSV readers are
implemented and tested for later source-specific adapters; no JSONL or CSV
dataset is projected yet.

## Identity rules

- A cycle uses its real `ScanRun.id`; a row without it is rejected.
- A signal uses its real `TradeSignal.id` when available.
- If a signal ID is absent, `projection_key` is a SHA-256 namespace key derived
  from `trade_signals` plus the stable, redacted source-record identity.
- `observation_id` remains `NULL` when the producer did not persist one.
- `cycle_id` on signals is recorded as evidence, but no foreign key is claimed
  because historical source completeness is not guaranteed.
- Source-record identities and evidence references are hashes or logical names;
  absolute paths are never stored.

## Consistency

Single JSON and CSV files use bounded pre/post metadata checks and retries.
JSONL uses inode-derived identity plus byte offset, stops before partial or
corrupt lines, and resets safely after truncation or rotation. Immutable JSON
file sets are snapshotted as a sorted list and upserted in one source
transaction. Constraints make repeated projection idempotent.

Finite writers use WAL while applying migrations or a source transaction, then
checkpoint and return the closed artifact to `journal_mode=DELETE`. This keeps
the completed file self-contained for atomic rebuild replacement and strictly
read-only API access; WAL/SHM files remain runtime-only and are never tracked.

No trade, outcome, cost, financial metric, agent, counterfactual, frontend, or
deployment functionality belongs to this phase.
