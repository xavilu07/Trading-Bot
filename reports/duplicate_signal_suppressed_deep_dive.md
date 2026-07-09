# duplicate_signal_suppressed Deep Dive

Generated at: 2026-06-22T16:08:45+00:00
Mode: offline analysis only. No strategy, scheduler, Telegram, filters or production behavior changed.

## 1. Exact origin

Primary file: `src/trading_signals/application/use_cases/run_market_scan.py`
Lifecycle file: `src/trading_signals/application/use_cases/signal_lifecycle.py`

### How it is generated
- `run_market_scan.build_signal_dedupe_key()` builds the signal dedupe key when each `TradeSignal` is created.
- `signal_repo.has_published_dedupe_key(signal.dedupe_key)` checks the latest 500 stored trade signals and returns true only if the exact same dedupe key already has `published_at`.
- `_no_send_reason()` returns `duplicate_signal_suppressed` when a valid signal is publishable by decision but exact dedupe is true.
- Later, valid but unpublished signals append `duplicate_signal_suppressed` to `evaluation.rejection_reasons` when `is_duplicate` is true.
- A second lifecycle layer, `classify_signal_lifecycle()`, blocks active same symbol+direction published signals unless reentry confirmation exists. That layer records reasons such as `active_same_symbol_direction_without_reentry`, not `duplicate_signal_suppressed`.

### Dedupe key
`symbol|decision|strategy_id|strategy_version|entry_timeframe|entry_snapshot.timestamp`

Window/cooldown: Exact dedupe has no time TTL; it scans the latest 500 stored trade signals for the same dedupe key with published_at. Lifecycle duplicate also has no fixed time TTL; it considers active published same symbol+direction entries from latest 500 signals.

Scope impact: The exact duplicate check sits before publish_signal and blocks public publish path. Paper/shadow paths are handled separately later; paper can still be rejected by its own candidate dedupe, but `duplicate_signal_suppressed` itself is a public/lifecycle publishing reason.

## 2. Source counts

| Source | Count |
|---|---:|
| scheduler_log_lines | 2 |
| scheduler_log_json_events | 2 |
| signals_log | 103 |
| shadow_signals | 0 |
| paper_rejection_context | 0 |
| trade_signals_total | 2069 |
| published_trade_signals | 10 |
| paper_closed_with_target | 0 |

## 3. Breakdowns

### symbol

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 103 | 100.0 | 0 | 0.0% | 0.0 | 0.0 |

### direction

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| long | 103 | 100.0 | 0 | 0.0% | 0.0 | 0.0 |

### setup_type

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| MAIN_SIGNAL | 103 | 100.0 | 0 | 0.0% | 0.0 | 0.0 |

### session

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 103 | 100.0 | 0 | 0.0% | 0.0 | 0.0 |

### market_regime

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| HIGH_VOLATILITY | 103 | 100.0 | 0 | 0.0% | 0.0 | 0.0 |

### entry_context

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| PULLBACK | 103 | 100.0 | 0 | 0.0% | 0.0 | 0.0 |

### score_bucket

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| 90+ | 103 | 100.0 | 0 | 0.0% | 0.0 | 0.0 |

## 4. Severe cases

- Score >= 70 blocked: 103
- Score >= 80 blocked: 103
- Score >= 90 blocked: 103
- RR valid blocked: 103
- Directional confluence passed blocked: 103
- Signal status valid blocked: 103

### Highest-score examples

| Symbol | Direction | Score | Setup | Session | Regime | Context | Dedupe key |
|---|---|---:|---|---|---|---|---|
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `9e4c535cde0217bccb99adaba94454125518c51d0d6ef4293d81817ae99d7d35` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `d8276bc53d1b6521e03d1b38febf426b1e205a3e984a119fd8b5d788b2f40c8c` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `2cb9424c177be05a09078cd58f4b969786ef64b8892cd2dd86fbe623b882c690` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `d0f72ff443e1cc0d9c0fc67b72d4ee3662154b01b31e52110e23eb520e142251` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `4cdd0c17d67f1158db3500a22040c9e08456967cc9621f02905018ff0d7673e3` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `d11931119e95913d3b2c753cd64314aed0e8cd935b8b7467314e636c581fe634` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `c1fc2fe62b90f297f6c0216ef13ba4d67885e19de7073c57bb91d5915ed6e93d` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `6801e44046037693aa939b5ecf73d9c2bd7c3f2723a843e9ef70e490c87dd31e` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `daed0290af6920868c823304181839ba28fd007f14521c41c09287d5055f6000` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `8455d4424774812414b0cd670bf6bd4bfdfb649a4e709013a6ee7b599e60819e` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `48e568177348c279d4e8ab4a4bd27ad72abdd2d53df989188ebbbaaebd68659c` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `4586b19dea95411ec9f12cfe385e870047623dfe4747887d062ec40b1b8733ab` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `5c59bfcc842b8cc66e233a14e807427418d9c2d2c440a4c5604b71d240faf314` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `6822b9c5a442e4831dda01f851e6976c41adf8059501427779eee23a0dfc85d4` |
| BTCUSDT | long | 100.0 | MAIN_SIGNAL | UNKNOWN | HIGH_VOLATILITY | PULLBACK | `d892c76badee5b644bd04f5f762ca391526d4e4735d37718baabf2b67c9eb731` |

## 5. Dedupe width analysis

- Events analyzed: 103
- Exact key matches against published signals: 0
- Broad symbol+direction matches against published signals: 103
- Events with exact key unavailable: 0
- Unique symbols: 1
- Unique symbol+direction pairs: 1
- Potentially too broad: True

### Top duplicate keys

| Dedupe key | Count |
|---|---:|
| `9e4c535cde0217bccb99adaba94454125518c51d0d6ef4293d81817ae99d7d35` | 1 |
| `d8276bc53d1b6521e03d1b38febf426b1e205a3e984a119fd8b5d788b2f40c8c` | 1 |
| `2cb9424c177be05a09078cd58f4b969786ef64b8892cd2dd86fbe623b882c690` | 1 |
| `d0f72ff443e1cc0d9c0fc67b72d4ee3662154b01b31e52110e23eb520e142251` | 1 |
| `4cdd0c17d67f1158db3500a22040c9e08456967cc9621f02905018ff0d7673e3` | 1 |
| `d11931119e95913d3b2c753cd64314aed0e8cd935b8b7467314e636c581fe634` | 1 |
| `c1fc2fe62b90f297f6c0216ef13ba4d67885e19de7073c57bb91d5915ed6e93d` | 1 |
| `6801e44046037693aa939b5ecf73d9c2bd7c3f2723a843e9ef70e490c87dd31e` | 1 |
| `daed0290af6920868c823304181839ba28fd007f14521c41c09287d5055f6000` | 1 |
| `8455d4424774812414b0cd670bf6bd4bfdfb649a4e709013a6ee7b599e60819e` | 1 |
| `48e568177348c279d4e8ab4a4bd27ad72abdd2d53df989188ebbbaaebd68659c` | 1 |
| `4586b19dea95411ec9f12cfe385e870047623dfe4747887d062ec40b1b8733ab` | 1 |

### Top broad symbol+direction pairs

| Pair | Count | Published active refs |
|---|---:|---:|
| BTCUSDT|long | 103 | 1 |

## 6. Paper evidence

- Closed paper rows with target: 0
- WR: 0.0%
- PF: 0.0
- Total R: 0.0
- Avg R: 0.0

Note: duplicate suppression is primarily a publication/lifecycle gate, so paper rows may be absent even when public publishing is blocked.

## 7. Data gaps

- No target records found in data/paper_trading/shadow_signals.csv.
- No target rows found in data/paper_trading/trades.csv; duplicate suppression likely blocks publication, not paper outcomes.

## 8. Conclusion

- Evidence classification: BROAD_ACTIVE_DUPLICATE
- Recommended action: permitir updates en vez de bloquear
- Rationale: No se observan coincidencias exactas, pero sí muchas coincidencias símbolo+dirección; conviene considerar updates/reentry controlado antes que republicar la misma operación.

Allowed actions considered: mantener dedupe actual, reducir ventana, hacer dedupe por dirección/símbolo/timeframe, permitir updates en vez de bloquear, permitir paper aunque público se bloquee, datos insuficientes.
