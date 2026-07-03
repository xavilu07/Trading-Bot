# ACTIVE_SIGNAL_CLEANUP_SHADOW_V1

Generated at: 2026-07-03T16:35:36+00:00
Mode: shadow diagnostic only. No active signal was closed, deleted, expired or republished.

## Executive Summary

- Total active signals: 10
- Likely zombie count: 10
- Stale count: 0
- duplicate_signal_suppressed events: 111
- Duplicates blocked by likely zombie: 111
- High score duplicates blocked by likely zombie: 110
- Estimated released candidates if cleanup: 111
- Runtime cleanup analysis events: 0
- Runtime cleanup candidate events: 0
- Recommendation: activar cleanup real

## Affected Symbol/Direction

| Pair | Active | Likely zombies | Stale | Duplicates | Score >= 90 duplicates |
|---|---:|---:|---:|---:|---:|
| BTCUSDT\|long | 1 | 1 | 0 | 110 | 110 |
| TAOUSDT\|long | 1 | 1 | 0 | 1 | 0 |
| BNBUSDT\|short | 1 | 1 | 0 | 0 | 0 |
| DOGEUSDT\|long | 1 | 1 | 0 | 0 | 0 |
| ETHUSDT\|long | 2 | 2 | 0 | 0 | 0 |
| ICPUSDT\|short | 1 | 1 | 0 | 0 | 0 |
| MANAUSDT\|short | 1 | 1 | 0 | 0 | 0 |
| XRPUSDT\|short | 2 | 2 | 0 | 0 | 0 |

## Active Signal Classifications

| Signal | Pair | Classification | Age h | Published at | Expires at | Close reason | Reasons |
|---|---|---|---:|---|---|---|---|
| `sig_77579d5442a1` | XRPUSDT\|short | LIKELY_ZOMBIE | 1586.28 | 2026-04-28T14:18:57.347717+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |
| `sig_23c36a41d54c` | XRPUSDT\|short | LIKELY_ZOMBIE | 1585.58 | 2026-04-28T15:00:45.166925+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |
| `sig_1631f34186d6` | BNBUSDT\|short | LIKELY_ZOMBIE | 1562.07 | 2026-04-29T14:31:33.492050+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |
| `sig_64286992bce9` | DOGEUSDT\|long | LIKELY_ZOMBIE | 1490.28 | 2026-05-02T14:18:47.675842+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |
| `sig_7b1b5db6a233` | ETHUSDT\|long | LIKELY_ZOMBIE | 1460.54 | 2026-05-03T20:02:59.793778+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |
| `sig_41eae3d19cc3` | TAOUSDT\|long | LIKELY_ZOMBIE | 1459.05 | 2026-05-03T21:32:48.922905+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |
| `sig_b6535ceaf589` | MANAUSDT\|short | LIKELY_ZOMBIE | 1458.52 | 2026-05-03T22:04:14.495927+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |
| `sig_e84f188ec9e5` | ICPUSDT\|short | LIKELY_ZOMBIE | 1458.52 | 2026-05-03T22:04:08.780604+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |
| `sig_257347cad0f9` | BTCUSDT\|long | LIKELY_ZOMBIE | 1440.93 | 2026-05-04T15:39:54.864055+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |
| `sig_d9bf53436cfa` | ETHUSDT\|long | LIKELY_ZOMBIE | 1440.93 | 2026-05-04T15:39:56.744863+00:00 | missing | missing | age_gt_48h, missing_expires_at, missing_close_reason |

## Runtime Shadow Logs

- `active_signal_cleanup_shadow_analysis`: 0
- `active_signal_cleanup_shadow_candidate`: 0

## Actionable Conclusion

Recommended action: **activar cleanup real**

- Hay señales activas clasificadas como LIKELY_ZOMBIE que están bloqueando candidatos nuevos.
- El siguiente paso seguro sería implementar cleanup real detrás de flag, no permitir duplicados directamente.

### Actions explicitly not taken

- No files deleted.
- No active signals closed.
- No duplicate publication enabled.
- No Telegram public changes.
