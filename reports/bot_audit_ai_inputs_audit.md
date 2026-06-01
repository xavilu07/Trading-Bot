# BOT_AUDIT_AI Inputs Audit

- Generated at: 2026-05-30T15:11:09+00:00
- Freshness threshold: 48.0 hours
- FOUND: 14
- MISSING: 2
- STALE: 1

| Input | Classification | Path | Exists | Freshness | Generator | Script OK | Rows | Size |
|---|---|---|---:|---|---|---:|---:|---:|
| canonical_trades | STALE | `data/paper_trading/trades.csv` | True | stale | `runtime: PaperTradingStore` | True | 49 | 67621 |
| intelligence_manifest | FOUND | `reports/intelligence_layer_manifest.json` | True | fresh | `scripts/generate_intelligence_reports.py` | True | 1 | 1009 |
| outcome_intelligence | FOUND | `reports/outcome_intelligence.csv` | True | fresh | `scripts/generate_outcome_intelligence.py` | True | 40 | 13157 |
| edge_breakdown | FOUND | `reports/edge_breakdown.csv` | True | fresh | `scripts/generate_performance_report.py` | True | 31 | 3519 |
| setup_rankings | FOUND | `reports/setup_rankings.csv` | True | fresh | `scripts/generate_setup_rankings.py` | True | 24 | 3215 |
| relaxation_shadow_v1_data_trades | MISSING | `data/shadow_relaxation/trades.csv` | False | missing | `runtime: RelaxationShadowV1Store` | True | 0 | 0 |
| relaxation_shadow_v1_data_skips | MISSING | `data/shadow_relaxation/skips.csv` | False | missing | `runtime: RelaxationShadowV1Store` | True | 0 | 0 |
| relaxation_shadow_v1_summary | FOUND | `reports/relaxation_shadow_v1_summary.csv` | True | fresh | `scripts/generate_relaxation_shadow_v1_summary.py` | True | 0 | 82 |
| relaxation_shadow_v1_skips | FOUND | `reports/relaxation_shadow_v1_skips.csv` | True | fresh | `scripts/generate_relaxation_shadow_v1_summary.py` | True | 0 | 78 |
| relaxation_shadow_v1_trades | FOUND | `reports/relaxation_shadow_v1_trades.csv` | True | fresh | `scripts/generate_relaxation_shadow_v1_summary.py` | True | 0 | 409 |
| relaxation_shadow_v2 | FOUND | `reports/relaxation_shadow_v2_intelligence.json` | True | fresh | `scripts/generate_relaxation_shadow_v2_intelligence.py` | True | 0 | 819 |
| context_toxicity | FOUND | `reports/context_toxicity_deep_dive.json` | True | fresh | `scripts/analyze_context_toxicity.py` | True | 1 | 525339 |
| post_consistency_edge | FOUND | `reports/post_consistency_edge_recalc.json` | True | fresh | `scripts/recalculate_post_consistency_edge.py` | True | 12 | 10272 |
| shadow_current_reject | FOUND | `reports/shadow_send_current_reject_deep_dive.json` | True | fresh | `scripts/analyze_shadow_send_current_reject.py` | True | 1 | 25293 |
| shadow_rejection_reasons | FOUND | `reports/shadow_send_current_reject_rejection_reasons.csv` | True | fresh | `scripts/analyze_shadow_send_current_reject.py` | True | 17 | 2803 |
| london_short_attribution | FOUND | `reports/london_short_edge_attribution.json` | True | fresh | `scripts/analyze_london_short_edge_attribution.py` | True | 1 | 33533 |
| range_penalty_shadow | FOUND | `reports/range_penalty_shadow.json` | True | fresh | `scripts/analyze_range_penalty_shadow.py` | True | 1 | 54511 |

## Details

### canonical_trades
- Classification: STALE
- Expected path: `data/paper_trading/trades.csv`
- Path correctness: True
- Generator: `runtime: PaperTradingStore`
- Generator exists: True
- Modified at: 2026-05-18T13:20:17+00:00
- Age hours: 289.85
- Reason: file_stale

### intelligence_manifest
- Classification: FOUND
- Expected path: `reports/intelligence_layer_manifest.json`
- Path correctness: True
- Generator: `scripts/generate_intelligence_reports.py`
- Generator exists: True
- Modified at: 2026-05-30T14:44:25+00:00
- Age hours: 0.45
- Reason: ok

### outcome_intelligence
- Classification: FOUND
- Expected path: `reports/outcome_intelligence.csv`
- Path correctness: True
- Generator: `scripts/generate_outcome_intelligence.py`
- Generator exists: True
- Modified at: 2026-05-30T14:44:24+00:00
- Age hours: 0.45
- Reason: ok

### edge_breakdown
- Classification: FOUND
- Expected path: `reports/edge_breakdown.csv`
- Path correctness: True
- Generator: `scripts/generate_performance_report.py`
- Generator exists: True
- Modified at: 2026-05-30T14:44:24+00:00
- Age hours: 0.45
- Reason: ok

### setup_rankings
- Classification: FOUND
- Expected path: `reports/setup_rankings.csv`
- Path correctness: True
- Generator: `scripts/generate_setup_rankings.py`
- Generator exists: True
- Modified at: 2026-05-30T14:44:24+00:00
- Age hours: 0.45
- Reason: ok

### relaxation_shadow_v1_data_trades
- Classification: MISSING
- Expected path: `data/shadow_relaxation/trades.csv`
- Path correctness: True
- Generator: `runtime: RelaxationShadowV1Store`
- Generator exists: True
- Modified at: n/a
- Age hours: None
- Reason: file_missing

### relaxation_shadow_v1_data_skips
- Classification: MISSING
- Expected path: `data/shadow_relaxation/skips.csv`
- Path correctness: True
- Generator: `runtime: RelaxationShadowV1Store`
- Generator exists: True
- Modified at: n/a
- Age hours: None
- Reason: file_missing

### relaxation_shadow_v1_summary
- Classification: FOUND
- Expected path: `reports/relaxation_shadow_v1_summary.csv`
- Path correctness: True
- Generator: `scripts/generate_relaxation_shadow_v1_summary.py`
- Generator exists: True
- Modified at: 2026-05-30T14:58:06+00:00
- Age hours: 0.22
- Reason: ok

### relaxation_shadow_v1_skips
- Classification: FOUND
- Expected path: `reports/relaxation_shadow_v1_skips.csv`
- Path correctness: True
- Generator: `scripts/generate_relaxation_shadow_v1_summary.py`
- Generator exists: True
- Modified at: 2026-05-30T14:58:06+00:00
- Age hours: 0.22
- Reason: ok

### relaxation_shadow_v1_trades
- Classification: FOUND
- Expected path: `reports/relaxation_shadow_v1_trades.csv`
- Path correctness: True
- Generator: `scripts/generate_relaxation_shadow_v1_summary.py`
- Generator exists: True
- Modified at: 2026-05-30T14:58:06+00:00
- Age hours: 0.22
- Reason: ok

### relaxation_shadow_v2
- Classification: FOUND
- Expected path: `reports/relaxation_shadow_v2_intelligence.json`
- Path correctness: True
- Generator: `scripts/generate_relaxation_shadow_v2_intelligence.py`
- Generator exists: True
- Modified at: 2026-05-30T14:44:21+00:00
- Age hours: 0.45
- Reason: ok

### context_toxicity
- Classification: FOUND
- Expected path: `reports/context_toxicity_deep_dive.json`
- Path correctness: True
- Generator: `scripts/analyze_context_toxicity.py`
- Generator exists: True
- Modified at: 2026-05-29T15:17:24+00:00
- Age hours: 23.9
- Reason: ok

### post_consistency_edge
- Classification: FOUND
- Expected path: `reports/post_consistency_edge_recalc.json`
- Path correctness: True
- Generator: `scripts/recalculate_post_consistency_edge.py`
- Generator exists: True
- Modified at: 2026-05-29T15:26:06+00:00
- Age hours: 23.75
- Reason: ok

### shadow_current_reject
- Classification: FOUND
- Expected path: `reports/shadow_send_current_reject_deep_dive.json`
- Path correctness: True
- Generator: `scripts/analyze_shadow_send_current_reject.py`
- Generator exists: True
- Modified at: 2026-05-29T15:30:44+00:00
- Age hours: 23.67
- Reason: ok

### shadow_rejection_reasons
- Classification: FOUND
- Expected path: `reports/shadow_send_current_reject_rejection_reasons.csv`
- Path correctness: True
- Generator: `scripts/analyze_shadow_send_current_reject.py`
- Generator exists: True
- Modified at: 2026-05-29T15:30:44+00:00
- Age hours: 23.67
- Reason: ok

### london_short_attribution
- Classification: FOUND
- Expected path: `reports/london_short_edge_attribution.json`
- Path correctness: True
- Generator: `scripts/analyze_london_short_edge_attribution.py`
- Generator exists: True
- Modified at: 2026-05-29T15:17:24+00:00
- Age hours: 23.9
- Reason: ok

### range_penalty_shadow
- Classification: FOUND
- Expected path: `reports/range_penalty_shadow.json`
- Path correctness: True
- Generator: `scripts/analyze_range_penalty_shadow.py`
- Generator exists: True
- Modified at: 2026-05-29T15:17:24+00:00
- Age hours: 23.9
- Reason: ok
