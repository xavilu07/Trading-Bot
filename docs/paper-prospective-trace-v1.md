# Prospective paper trace v1

## Purpose and scope

This trace captures simulated paper evidence prospectively. It is disabled by
default, does not place an exchange order, and is not a source of real fills.
The operational producers remain independent from FastAPI and the dashboard.
The dashboard SQLite database is only a rebuildable projection.

No existing paper-tracker row is promoted into a receipt. Historical signals
remain readable with their older schemas, but missing prospective identity and
events are not inferred retroactively.

## Audited legacy flow

The current scan obtains entry and higher-timeframe snapshots, updates the
mutable paper tracker, evaluates the strategy, persists the evaluation and risk
plan, persists `TradeSignal`, applies publication decisions, and finally
upserts a paper candidate.

The setup origin is available before the result:

- `primary_sweep_setup` in `StrategyEvaluation.passed_filters` maps to
  `liquidity-sweep-primary` v1.
- `secondary_setup` maps to `break-of-structure-secondary` v1.

No fallback setup is accepted in strict trace mode. The risk plan has one
stored `take_profit`. The existing candidate builder names that level TP2 and
the existing tracker uses it as the winning terminal barrier; the prospective
identity therefore records it as `FINAL_TARGET`, index 2. This does not imply
that TP1, partial exits, break-even, or trailing stops exist.

The mutable tracker cannot act as a receipt source because it:

- creates an open trade without a distinct order, touch, fill, and position;
- overwrites state instead of retaining events;
- increments `candles_held` once per scheduler scan;
- can process the same hourly candle repeatedly and does not explicitly reject
  an open candle;
- resolves an OHLC stop/target collision by checking stop first;
- expires after scans rather than unique closed candles;
- lacks a demonstrated terminal fill for expiry.

## Entities and receipts

A signal is a strategy decision. A paper order is the simulated intent waiting
for entry. `ENTRY_TOUCHED` is OHLC evidence only. A simulated fill is an
explicit model output and never an exchange fill. A position exists only after
that simulated fill. An exit requires separate barrier or time-exit evidence.
A signal that never activates is distinct from a position that reaches its
horizon.

Receipts are canonical JSON records written one per JSONL line. Each contains
stable entity identity, sequence, previous receipt ID, evidence fingerprint,
policy/model versions, reason code, UTC timestamps, and a hash of the complete
unsigned receipt. The chain is per trace, so traces may safely interleave.
Duplicate receipt IDs with identical hashes are idempotent; collisions,
truncation, invalid JSON, altered hashes, broken chains, and out-of-order
events fail closed.

The supported event vocabulary is defined in
`trading_signals.paper_trace.contracts.ReceiptEventType`. State is rebuilt by
replay and is never the primary mutable evidence.

## Frozen fill and expiry policy

`paper-closed-bar-touch-modeled-fill-v1` uses 1h, unique, chronologically
contiguous, fully closed candles. Evaluation starts at the first timeframe
boundary at or after `decision_at`. Scheduler scan count is irrelevant.

An unambiguous closed-bar range touch emits `ENTRY_TOUCHED`. It then emits a
separate `SIMULATED_FILL_CREATED` whose modeled price is the fixed entry level,
followed by `PAPER_POSITION_OPENED`. Quantity remains absent. A gap that crosses
entry without a tradable range touch is ambiguous and creates no fill. If entry
and a barrier occur in one OHLC candle and entry was not known at the open,
intrabar order is unknown and no fill is asserted.

For an existing position, a single stop or final-target touch closes the
simulated position. A candle touching both is `EXIT_AMBIGUOUS`. A gap beyond a
barrier uses the observed next candle open only as an explicitly modeled paper
exit. Different semantics require a new policy version and checksum.

Entry has a 24-closed-candle horizon. Position time starts after the fill
candle and also has 24 closed candles. The default expiry policy is
`position-expired-unresolved-v1`: it emits `POSITION_HORIZON_REACHED` and
`POSITION_EXPIRED_UNRESOLVED`, without price or R.

Alternative close-at-horizon, extend-until-barrier, and time-stop approaches
are intentionally not activated. Each would require a separate, non-canonical
version and must never be mixed with the default policy.

Fees default to `NO_FEE_MODEL`; slippage defaults to `NO_SLIPPAGE_MODEL`.
No net R, fee, slippage, quantity, capital, or leverage is invented.

## Store and recovery

The selected operational boundary is a separate append-only JSONL file:

- no dependency on dashboard SQLite, FastAPI, or the operational container;
- explicit absolute `.jsonl` path required;
- an explicit allowed runtime root is required;
- paths beneath the bot data root, paths outside that root, and symlinks are
  rejected;
- the parent must be owned by the runtime user with no group/other access;
- existing store files must be regular, owned by the runtime user, and have no
  group/other access; reads and writes use `O_NOFOLLOW`;
- advisory exclusive lock, `O_APPEND`, complete canonical line, flush, and
  file plus parent-directory `fsync` before success;
- mode `0600`;
- an explicit maximum byte capacity is required by runtime configuration;
- complete final newline required;
- hash-chain verification on every read and before append.

The writer never repairs a corrupt or truncated store automatically. Recovery
copies the last known valid file to a new safe path, validates the chain, and
then changes configuration in a separately approved deployment. Rotation is
not implemented in v1. The Phase 6 shadow window therefore uses a hard
capacity limit and read-only monitoring; reaching the limit isolates trace
collection without affecting the scanner. Segmented rotation remains a
separate design before indefinite operation.

## Feature flags

All defaults are inert:

```text
PAPER_TRACE_ENABLED=false
PAPER_TRACE_STORE_PATH=
PAPER_TRACE_ALLOWED_ROOT=
PAPER_TRACE_MAX_BYTES=
PAPER_FILL_POLICY_ID=paper-closed-bar-touch-modeled-fill-v1
PAPER_EXPIRY_POLICY_ID=position-expired-unresolved-v1
PAPER_FEE_MODEL_ID=NO_FEE_MODEL
PAPER_SLIPPAGE_MODEL_ID=NO_SLIPPAGE_MODEL
PAPER_TRACE_STRICT_IDENTITY=true
```

Disabled means no path resolution, file creation, lock, thread, process,
network request, Telegram message, or behavior change. Enabled without an
explicit safe path, allowed root, and positive byte limit fails closed; there
is no fallback under `data`. Configuration and runtime trace errors are logged
with a sane code, open a process-local circuit breaker, and disable only shadow
trace collection. They never abort a symbol scan, alter a paper candidate, or
change publication.

## Manual validation, replay, and projection

The CLI is finite and network-free:

```text
python -m trading_signals.paper_trace.cli trace-policy
python -m trading_signals.paper_trace.cli trace-simulate --dry-run
python -m trading_signals.paper_trace.cli trace-validate --store-path <trace.jsonl> --data-root <protected-data-root> --allowed-root <runtime-root> --max-bytes <limit>
python -m trading_signals.paper_trace.cli trace-inspect --store-path <trace.jsonl> --data-root <protected-data-root> --allowed-root <runtime-root> --trace-id <id>
python -m trading_signals.paper_trace.cli trace-replay --store-path <trace.jsonl> --data-root <protected-data-root> --allowed-root <runtime-root> --trace-id <id>
python -m trading_signals.paper_trace.cli trace-store-health --store-path <trace.jsonl> --data-root <protected-data-root> --allowed-root <runtime-root> --max-bytes <limit>
python -m trading_signals.paper_trace.cli trace-project --store-path <trace.jsonl> --data-root <protected-data-root> --allowed-root <runtime-root> --sqlite-path <temporary.sqlite> --dry-run
```

`trace-project` verifies receipts and replay before writing only to the
configured dashboard SQLite. It labels the source
`PROSPECTIVE_PAPER_TRACE`, never modifies JSONL, and does not run historical
ingestion, outcomes, or metrics. No public API route is added.

## Future activation and rollback

A future shadow deployment must first create and permission a dedicated runtime
directory, validate policy checksum and identity against the exact release,
enable the flag only in that isolated release, observe resource usage, and
verify receipts independently before using them analytically.

Rollback is disabling `PAPER_TRACE_ENABLED` and restarting only during an
explicitly approved maintenance action. The append-only store remains evidence
and must not be deleted. This phase neither changes production configuration
nor performs that activation.

## Limitations

OHLC cannot prove intrabar sequence or a real executable price. There are no
exchange acknowledgements, fill receipts, quantity, fees, slippage, partial
exits, trailing stop, break-even, or monetary PnL. Correlation group and agent
decision ID remain absent unless a producer provides them prospectively.
JSONL rotation and multi-host coordination require a future design. Receipts
describe a simulation, never real trading.

## Phase 6 audit corrections

The independent activation audit found and corrected three release blockers:

- trace exceptions previously escaped into the per-symbol operational handler;
- Binance's `close_time` is one millisecond before the timeframe boundary,
  while Bybit reports the boundary, so subtracting one duration directly could
  skip the first eligible hourly candle;
- an existing file with unsafe permissions and a path-swap race were not
  rejected.

The adapter now accepts only exact close boundaries or the demonstrated
sub-two-second pre-boundary representation and normalizes evidence to exact UTC
open/close boundaries. The market provider is included in the evidence
fingerprint. Ambiguous entry at the last entry-horizon candle remains ambiguous
and is not also mislabeled as never activated.

For the initial 72-hour shadow window, a conservative upper bound is 504 new
traces (seven symbols times 24 hourly candles times three days), approximately
56 receipts per trace. At the measured synthetic average of roughly 1.5 KiB
per receipt this is about 42 MiB. A 256 MiB hard limit provides more than six
times that bound, while read-only monitoring alerts at 75 percent. This bound
does not justify indefinite operation or remove the need for segmented
rotation.
