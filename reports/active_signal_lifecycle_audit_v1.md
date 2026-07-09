# ACTIVE_SIGNAL_LIFECYCLE_AUDIT_V1

Generated at: 2026-07-03T16:29:44+00:00
Mode: offline diagnostic only. No signals were closed, deleted, republished or modified.

## Executive Summary

- Active signals count: 10
- Published signals count: 10
- Rejected signals count: 2032
- Valid unpublished count: 27
- Active without explicit expiration: 10
- Active without close reason: 10
- duplicate_signal_suppressed events: 111
- Oldest active signal age hours: 1586.18
- Recommendation: añadir expiration cleanup

## 1. Lifecycle Code Behavior

- `active_published_signals()` treats any latest-500 `trade_signals` record with `published_at` and same symbol/direction as active.
- `signal_lifecycle.py` blocks when active count is too high or reentry confirmation fails; it does not expire or close active signals.
- `run_market_scan.py` saves published signals with `status=published` and `published_at`, but no lifecycle expiration is stored there.
- `trade_signals` stores rejected, valid-unpublished and published records together by date folders.

## 2. Active By Symbol/Direction

| Pair | Active | Duplicates blocked | Oldest published at |
|---|---:|---:|---|
| BTCUSDT\|long | 1 | 110 | 2026-05-04T15:39:54.864055+00:00 |
| TAOUSDT\|long | 1 | 1 | 2026-05-03T21:32:48.922905+00:00 |
| XRPUSDT\|short | 2 | 0 | 2026-04-28T14:18:57.347717+00:00 |
| BNBUSDT\|short | 1 | 0 | 2026-04-29T14:31:33.492050+00:00 |
| DOGEUSDT\|long | 1 | 0 | 2026-05-02T14:18:47.675842+00:00 |
| ETHUSDT\|long | 2 | 0 | 2026-05-03T20:02:59.793778+00:00 |
| MANAUSDT\|short | 1 | 0 | 2026-05-03T22:04:14.495927+00:00 |
| ICPUSDT\|short | 1 | 0 | 2026-05-03T22:04:08.780604+00:00 |

## 3. Active Signals

| Signal | Pair | Published at | Age h | Entry | SL | TP | Status | Lifecycle | Expiration | Close reason | Duplicates |
|---|---|---|---:|---:|---:|---:|---|---|---|---|---:|
| `sig_257347cad0f9` | BTCUSDT\|long | 2026-05-04T15:39:54.864055+00:00 | 1440.83 | 80216.16 | 78059.472429 | 84529.535143 | published | NEW | missing | missing | 110 |
| `sig_41eae3d19cc3` | TAOUSDT\|long | 2026-05-03T21:32:48.922905+00:00 | 1458.95 | 293.3 | 281.142857 | 317.614286 | published | NEW | missing | missing | 1 |
| `sig_23c36a41d54c` | XRPUSDT\|short | 2026-04-28T15:00:45.166925+00:00 | 1585.48 | 1.3699 | 1.403561 | 1.302577 | published | None | missing | missing | 0 |
| `sig_77579d5442a1` | XRPUSDT\|short | 2026-04-28T14:18:57.347717+00:00 | 1586.18 | 1.3781 | 1.403494 | 1.327312 | published | None | missing | missing | 0 |
| `sig_1631f34186d6` | BNBUSDT\|short | 2026-04-29T14:31:33.492050+00:00 | 1561.97 | 622.17 | 630.106429 | 606.297143 | published | NEW | missing | missing | 0 |
| `sig_64286992bce9` | DOGEUSDT\|long | 2026-05-02T14:18:47.675842+00:00 | 1490.18 | 0.1086 | 0.107024 | 0.111752 | published | NEW | missing | missing | 0 |
| `sig_7b1b5db6a233` | ETHUSDT\|long | 2026-05-03T20:02:59.793778+00:00 | 1460.45 | 2335.59 | 2295.654143 | 2415.461714 | published | NEW | missing | missing | 0 |
| `sig_b6535ceaf589` | MANAUSDT\|short | 2026-05-03T22:04:14.495927+00:00 | 1458.43 | 0.0882 | 0.090911 | 0.082777 | published | NEW | missing | missing | 0 |
| `sig_e84f188ec9e5` | ICPUSDT\|short | 2026-05-03T22:04:08.780604+00:00 | 1458.43 | 2.337 | 2.372614 | 2.265772 | published | NEW | missing | missing | 0 |
| `sig_d9bf53436cfa` | ETHUSDT\|long | 2026-05-04T15:39:56.744863+00:00 | 1440.83 | 2371.39 | 2304.380857 | 2505.408286 | published | NEW | missing | missing | 0 |

## 4. Duplicate Attribution

| Active key | Signal | Pair | Duplicates | Score >= 90 | Latest duplicate |
|---|---|---|---:|---:|---|
| `BTCUSDT\|long` | `sig_257347cad0f9` | BTCUSDT\|long | 110 | 110 | 2026-07-03T16:21:40.083254+00:00 |
| `TAOUSDT\|long` | `sig_41eae3d19cc3` | TAOUSDT\|long | 1 | 0 | None |
| `XRPUSDT\|short` | `sig_23c36a41d54c` | XRPUSDT\|short | 0 | 0 | None |
| `XRPUSDT\|short` | `sig_77579d5442a1` | XRPUSDT\|short | 0 | 0 | None |
| `BNBUSDT\|short` | `sig_1631f34186d6` | BNBUSDT\|short | 0 | 0 | None |
| `DOGEUSDT\|long` | `sig_64286992bce9` | DOGEUSDT\|long | 0 | 0 | None |
| `ETHUSDT\|long` | `sig_7b1b5db6a233` | ETHUSDT\|long | 0 | 0 | None |
| `MANAUSDT\|short` | `sig_b6535ceaf589` | MANAUSDT\|short | 0 | 0 | None |
| `ICPUSDT\|short` | `sig_e84f188ec9e5` | ICPUSDT\|short | 0 | 0 | None |
| `ETHUSDT\|long` | `sig_d9bf53436cfa` | ETHUSDT\|long | 0 | 0 | None |

## 5. Store Mixing

- trade_signals total: 2069
- published: 10
- rejected: 2032
- valid_unpublished: 27
- published and rejected mixed in same store: True

## 6. Closure / Invalidation

- `signal_lifecycle.py` only reads published signals and returns NEW/REENTRY/DUPLICATE; it does not clean or expire active records.
- `trade_signals` published records do not store TP/SL/expiration close state directly.
- Live/paper outcomes may exist elsewhere, but lifecycle active state is not derived from those close events.
- No active published signal has close_reason in the inspected data.

### Current price invalidation

- No active signal could be proven invalidated from available current_price + entry/SL/TP data.

## 7. Data Gaps

- Active published signals lack explicit expires_at.
- Active published signals lack close_reason/exit_reason.

## 8. Actionable Conclusion

Recommended action: **añadir expiration cleanup**

- Las señales publicadas se consideran activas por published_at y same symbol/direction, pero no tienen expiration explícita.
- No hay close_reason en señales activas; lifecycle no sabe si TP/SL/expiration ya cerró la idea.
- Hay duplicados atribuidos a señales activas; antes de permitir reentry conviene registrar/limpiar estado activo.

### Actions explicitly not taken

- No files deleted.
- No active signals closed.
- No duplicate publication enabled.
- No Telegram public changes.
