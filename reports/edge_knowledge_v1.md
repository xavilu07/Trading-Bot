# Edge Knowledge Base V1

Generated at: 2026-07-01T14:45:10+00:00
Source report: `reports/performance_intelligence_report_v2.json`

## Summary

- Priority edges: 0
- Avoid edges: 0
- Watch edges: 21
- Total edges: 21

## Priority Edges

_No edges._

## Avoid Edges

_No edges._

## Watch Edges

| ID | Context | Weight | Confidence | Evidence | PF | TotalR | AvgR | Hint |
|---|---|---:|---|---:|---:|---:|---:|---|
| `edge_v1_f1814de42252` | {'direction': 'short'} | -3.9191 | MEDIUM | 21 | 0.3296 | -9.8004 | -0.4667 | WATCH |
| `edge_v1_543c09ff0631` | {'direction': 'long'} | 3.8005 | MEDIUM | 20 | 1.872 | 7.225 | 0.3613 | WATCH |
| `edge_v1_5d1d79d8d886` | {'nearest_distance_to_liquidity_atr_bucket': '1-2'} | -2.6988 | MEDIUM | 20 | 0.472 | -6.2266 | -0.3113 | WATCH |
| `edge_v1_3320c1e3537e` | {'direction': 'long', 'setup_type': 'MAIN_SIGNAL'} | 2.711 | MEDIUM | 15 | 1.8455 | 5.9188 | 0.3946 | WATCH |
| `edge_v1_7e48cb6c5d65` | {'directional_distance_to_liquidity_atr_bucket': '2-3'} | -2.1341 | MEDIUM | 19 | 0.6002 | -5.311 | -0.2795 | WATCH |
| `edge_v1_9394eb5c4d38` | {'nearest_distance_to_liquidity_atr_bucket': '0.5-1'} | 2.3231 | MEDIUM | 15 | 1.7041 | 5.1977 | 0.3465 | WATCH |
| `edge_v1_66419ea32c2c` | {'liquidity_sweep': 'none'} | -2.0282 | MEDIUM | 18 | 0.5007 | -4.4452 | -0.247 | WATCH |
| `edge_v1_a02157ccbf1a` | {'setup_type': 'SECONDARY_SIGNAL'} | -2.0282 | MEDIUM | 18 | 0.5007 | -4.4452 | -0.247 | WATCH |
| `edge_v1_4fbabc68be90` | {'trend_4h': 'bearish'} | -1.8072 | MEDIUM | 25 | 0.7157 | -4.1466 | -0.1659 | WATCH |
| `edge_v1_7f54c063b423` | {'market_regime': 'RANGING'} | -1.7049 | MEDIUM | 18 | 0.6171 | -4.0123 | -0.2229 | WATCH |
| `edge_v1_8b842c4b63e3` | {'break_of_structure': 'bearish_bos'} | -1.4938 | MEDIUM | 20 | 0.6991 | -3.4962 | -0.1748 | WATCH |
| `edge_v1_9e0496e11a4d` | {'late_entry_from_bos': 'false'} | -1.0223 | HIGH | 41 | 0.8876 | -2.5754 | -0.0628 | WATCH |
| `edge_v1_af7e99dcb10f` | {'paper_level': 'HIGH'} | -1.0223 | HIGH | 41 | 0.8876 | -2.5754 | -0.0628 | WATCH |
| `edge_v1_f8977cf3344e` | {'rr_valid': 'true'} | -1.0223 | HIGH | 41 | 0.8876 | -2.5754 | -0.0628 | WATCH |
| `edge_v1_933e16108acf` | {'break_of_structure': 'none'} | -0.7423 | MEDIUM | 15 | 0.8115 | -1.8854 | -0.1257 | WATCH |
| `edge_v1_15cf279c5254` | {'setup_type': 'MAIN_SIGNAL'} | 0.9843 | MEDIUM | 23 | 1.1336 | 1.8698 | 0.0813 | WATCH |
| `edge_v1_4bef77fcdff5` | {'trend_1h': 'bullish'} | -0.6812 | MEDIUM | 23 | 0.8633 | -1.684 | -0.0732 | WATCH |
| `edge_v1_9549f3a67500` | {'trend_4h': 'bullish'} | 0.7062 | MEDIUM | 16 | 1.1889 | 1.5712 | 0.0982 | WATCH |
| `edge_v1_5f915114d363` | {'trade_location': 'near_support'} | 0.6513 | MEDIUM | 15 | 1.1873 | 1.5189 | 0.1013 | WATCH |
| `edge_v1_024363b12997` | {'entry_context': 'BREAKOUT'} | 0.5817 | MEDIUM | 23 | 1.0825 | 0.8996 | 0.0391 | WATCH |
| `edge_v1_56dc81e5a282` | {'trend_1h': 'bearish'} | -0.348 | MEDIUM | 18 | 0.9158 | -0.8914 | -0.0495 | WATCH |

## API Contract

`load_edge_knowledge()` loads `data/edge_knowledge/knowledge_v1.json`.
`evaluate_context(context)` returns `{bonus, matched_edges, confidence}`.

This layer is offline/shadow only and does not change production decisions.
