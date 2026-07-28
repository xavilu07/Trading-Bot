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

## Canonical outcome policy

Migration `0002` adds a reproducible outcome projection without changing the
source-of-truth boundary. `outcomes-once` reads directional signals from this
read model, joins their original risk plans read-only, and evaluates local
`market_snapshots`. It writes only to the configured SQLite database.

The default `closed-bars-entry-touch-v1` policy:

- uses unique, contiguous, closed candles of the signal timeframe;
- starts at the first complete UTC-aligned candle whose open is not before the
  persisted decision timestamp;
- requires the intended entry price to be touched after the decision because
  no execution receipt currently proves a fill at the historical close;
- consumes the horizon in real timeframe candles, never scheduler cycles;
- returns `AMBIGUOUS` if entry/barrier ordering or stop/target ordering cannot
  be established from OHLC;
- returns `NO_MARKET_DATA` for a past missing candle and `OPEN` only while the
  next required candle has not closed;
- fingerprints the exact evidence used, so a changed price path produces a
  separate row instead of overwriting prior evidence.

Resolving an intrabar collision as fact would require a separately
fingerprinted, reliable lower-timeframe source covering that candle. No such
source is downloaded or inferred by this phase.

The alternative stop-first and target-first collision policies are retained
only as explicitly `NON_CANONICAL` analytical variants. The read-only API does
not expose outcomes in this phase and continues to report
`outcomes_canonical=false`.

The old paper tracker is intentionally not reused. It incremented
`candles_held` once per scheduler scan, even when repeated scans carried the
same 1h snapshot, and checked stop before target inside one OHLC candle. With a
15-minute scheduler this made a 24-candle horizon expire in roughly six hours
and silently resolved intrabar collisions as losses.

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

No aggregate financial metric, cost model, agent receipt, counterfactual,
frontend, public outcome endpoint, or deployment functionality belongs to this
phase.
