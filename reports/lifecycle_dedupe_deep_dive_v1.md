# LIFECYCLE_DEDUPE_DEEP_DIVE_V1

Generated at: 2026-07-03T16:17:48+00:00
Mode: offline diagnostic only. No production behavior changed.

## Executive Summary

- duplicate_signal_suppressed: 110
- paper_rejected_duplicate: 11
- score >= 90 duplicates: 109
- RR valid duplicates: 1
- Directional confluence passed duplicates: 1
- SIGNAL_UPDATE_V1 events: 0
- Recommendation: mejorar SIGNAL_UPDATE_V1

## 1. Code Origin

- `run_market_scan.build_signal_dedupe_key()` builds `symbol|decision|strategy_id|strategy_version|entry_timeframe|entry_snapshot.timestamp`.
- `FileSignalRepository.has_published_dedupe_key()` checks latest 500 `trade_signals` for the exact same `dedupe_key` with `published_at`.
- `_no_send_reason()` returns `duplicate_signal_suppressed` when a valid publishable signal has exact duplicate=true.
- Later in the valid-but-not-published branch, `evaluation.rejection_reasons.append('duplicate_signal_suppressed')` records the block.

### paper_rejected_duplicate

- `PaperTradingStore.upsert_candidate()` rejects if any existing paper trade has the same candidate `dedupe_key`.
- `run_market_scan.py` maps that false upsert to `paper_rejected_duplicate` for main paper and candidate paper flows.
- Paper dedupe is separate from public signal dedupe; it does not require Telegram publication.

### Active signal state

- `signal_lifecycle.active_published_signals()` treats any latest-500 signal with matching `symbol`, `decision` and `published_at` as active.
- There is no explicit TTL/expiry check in `active_published_signals()`; active state is inferred from published signal records.
- `classify_signal_lifecycle()` allows `REENTRY` only when max reentries not exceeded and `has_reentry_confirmation()` passes.
- `SIGNAL_UPDATE_V1` observes duplicate/lifecycle blocks only after the valid signal reaches the duplicate/lifecycle branch.

## 2. Source Counts

| Source | Count |
|---|---:|
| signals_log_rows | 466 |
| scheduler_json_events | 2287 |
| trade_signals_json | 2069 |
| published_trade_signals | 10 |
| signal_deliveries_json | 37 |
| paper_trade_rows | 49 |
| duplicate_signal_suppressed | 110 |
| paper_rejected_duplicate | 11 |

## 3. Dedupe Width

- Events analyzed: 110
- Exact dedupe key matches: 0
- Missing dedupe key events: 110
- Broad symbol+direction active matches: 110
- Potentially too broad: True

### Top symbol+direction pairs

| Pair | Duplicates | Published refs |
|---|---:|---:|
| BTCUSDT|long | 109 | 1 |
| TAOUSDT|long | 1 | 1 |

## 4. Duplicate Breakdowns

### symbol

| Value | Count | Avg score | Score >= 90 | RR valid | Confluence passed |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | 109 | 100.0 | 109 | 0 | 0 |
| TAOUSDT | 1 | 60.0 | 0 | 1 | 1 |

### direction

| Value | Count | Avg score | Score >= 90 | RR valid | Confluence passed |
|---|---:|---:|---:|---:|---:|
| long | 110 | 99.6364 | 109 | 1 | 1 |

### setup_type

| Value | Count | Avg score | Score >= 90 | RR valid | Confluence passed |
|---|---:|---:|---:|---:|---:|
| MAIN_SIGNAL | 109 | 100.0 | 109 | 0 | 0 |
| SECONDARY_SIGNAL | 1 | 60.0 | 0 | 1 | 1 |

### score_bucket

| Value | Count | Avg score | Score >= 90 | RR valid | Confluence passed |
|---|---:|---:|---:|---:|---:|
| 90+ | 109 | 100.0 | 109 | 0 | 0 |
| 60-69 | 1 | 60.0 | 0 | 1 | 1 |

### session

| Value | Count | Avg score | Score >= 90 | RR valid | Confluence passed |
|---|---:|---:|---:|---:|---:|
| UNKNOWN | 109 | 100.0 | 109 | 0 | 0 |
| NEW_YORK | 1 | 60.0 | 0 | 1 | 1 |

### market_regime

| Value | Count | Avg score | Score >= 90 | RR valid | Confluence passed |
|---|---:|---:|---:|---:|---:|
| HIGH_VOLATILITY | 110 | 99.6364 | 109 | 1 | 1 |

### entry_context

| Value | Count | Avg score | Score >= 90 | RR valid | Confluence passed |
|---|---:|---:|---:|---:|---:|
| PULLBACK | 109 | 100.0 | 109 | 0 | 0 |
| BREAKOUT | 1 | 60.0 | 0 | 1 | 1 |

### trade_location

| Value | Count | Avg score | Score >= 90 | RR valid | Confluence passed |
|---|---:|---:|---:|---:|---:|
| UNKNOWN | 109 | 100.0 | 109 | 0 | 0 |
| near_resistance | 1 | 60.0 | 0 | 1 | 1 |

## 5. Severe Cases

- Score >= 70: 109
- Score >= 80: 109
- Score >= 90: 109
- RR valid: 1
- Directional confluence passed: 1
- Signal status valid: 109

### Highest score examples

| Symbol | Direction | Score | Setup | Session | Regime | Entry context | Reason source |
|---|---|---:|---|---|---|---|---|
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | signals_log |

## 6. SIGNAL_UPDATE_V1 Coverage

- Total events: 0
- New snapshot true: 0
- Reentry confirmation true: 0

| Update type | Count |
|---|---:|
| STRENGTHENED_SIGNAL | 0 |
| REENTRY_CANDIDATE | 0 |
| INVALIDATION_WARNING | 0 |
| NO_UPDATE | 0 |

### SIGNAL_UPDATE_V1 assessment

- No runtime SIGNAL_UPDATE_V1 events found; current duplicate cases are not being captured or local logs predate runtime deployment.
- SIGNAL_UPDATE_V1 report confirms duplicate_signal_suppressed still blocks publication.

## 7. Paper duplicate diagnostics

- Scheduler paper duplicates: 11
- Paper CSV rows containing duplicate reason: 0
- Existing open paper trades: 8

| Dimension | Top value | Count |
|---|---|---:|
| symbol | ETHUSDT | 1 |
| direction | UNKNOWN | 11 |
| session | NEW_YORK | 9 |
| market_regime | TRENDING | 4 |
| entry_context | PULLBACK | 4 |
| score_bucket | 50-59 | 4 |

## 8. Data gaps

- No SIGNAL_UPDATE_V1 runtime events found; cannot verify live classification coverage.
- trade_signals active-state model has no explicit TP/SL/expiration/invalidation close marker.
- Some duplicate events lack the original signal dedupe key; exact-vs-broad analysis is partial.

## 9. Actionable conclusion

Recommended action: **mejorar SIGNAL_UPDATE_V1**

- Hay duplicados, pero no hay eventos runtime de SIGNAL_UPDATE_V1 que demuestren clasificación efectiva.
- La capa active same symbol+direction no tiene expiración efectiva en trade_signals; cualquier señal publicada reciente puede permanecer activa en la ventana latest-500.
- La evidencia disponible sugiere mezcla entre dedupe exacto y bloqueo amplio symbol+direction; conviene separar dedupe público exacto de lifecycle/reentry.
- paper_rejected_duplicate usa dedupe independiente de paper; conviene auditar si paper debe permitir reentries aunque público siga bloqueado.

### Actions explicitly not taken

- No duplicate publication enabled.
- No Telegram public changes.
- No filter or strategy changes.
