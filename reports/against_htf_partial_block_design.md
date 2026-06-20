# AGAINST_HTF_PARTIAL_BLOCK_DESIGN

Generated at: 2026-06-05T17:09:47+00:00
Data path: data
Method: Exclude bullish_sweep, isolate against_htf, then simulate candidate partial blocks.

## Executive Summary

- Baseline against_htf: trades=19, WR=36.84%, PF=1.0493, TotalR=0.4942, AvgR=0.026
- Best candidate: against_htf AND low_volume (removed=4, PF 1.0493->1.4386, R improvement=2.5896, profitable lost=1, class=WATCH)
- Safest candidate: against_htf AND low_volume (removed=4, PF 1.0493->1.4386, R improvement=2.5896, profitable lost=1, class=WATCH)
- Highest PF improvement: against_htf AND low_volume (removed=4, PF 1.0493->1.4386, R improvement=2.5896, profitable lost=1, class=WATCH)
- Lowest collateral damage: against_htf AND low_volume AND BREAKOUT (removed=1, PF 1.0493->1.1655, R improvement=1.0, profitable lost=0, class=WATCH)
- Recommended shadow filter: against_htf AND SECONDARY_SIGNAL (removed=6, PF 1.0493->1.0768, R improvement=0.1204, profitable lost=2, class=SHADOW_TEST)

## Filter Ranking

| Candidate | Removed | PF Before | PF After | TotalR Before | TotalR After | WR Delta | R Improvement | Profitable Lost | Losing Removed | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf AND low_volume | 4 | 1.0493 | 1.4386 | 0.4942 | 3.0838 | 3.16 | 2.5896 | 1 | 3 | WATCH |
| against_htf AND low_volume AND BREAKOUT | 1 | 1.0493 | 1.1655 | 0.4942 | 1.4942 | 2.05 | 1.0 | 0 | 1 | WATCH |
| against_htf AND SECONDARY_SIGNAL | 6 | 1.0493 | 1.0768 | 0.4942 | 0.6146 | 1.62 | 0.1204 | 2 | 4 | SHADOW_TEST |
| against_htf AND session=ASIA | 0 | 1.0493 | 1.0493 | 0.4942 | 0.4942 | 0.0 | 0.0 | 0 | 0 | REJECT |
| against_htf AND ASIA AND low_volume | 0 | 1.0493 | 1.0493 | 0.4942 | 0.4942 | 0.0 | 0.0 | 0 | 0 | REJECT |
| against_htf AND ASIA AND BREAKOUT | 0 | 1.0493 | 1.0493 | 0.4942 | 0.4942 | 0.0 | 0.0 | 0 | 0 | REJECT |
| against_htf AND BREAKOUT | 8 | 1.0493 | 0.9321 | 0.4942 | -0.475 | -0.48 | -0.9692 | 3 | 5 | REJECT |

## Candidate Details

| Candidate | Removed | PF Before | PF After | TotalR Before | TotalR After | WR Delta | R Improvement | Profitable Lost | Losing Removed | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf AND session=ASIA | 0 | 1.0493 | 1.0493 | 0.4942 | 0.4942 | 0.0 | 0.0 | 0 | 0 | REJECT |
| against_htf AND low_volume | 4 | 1.0493 | 1.4386 | 0.4942 | 3.0838 | 3.16 | 2.5896 | 1 | 3 | WATCH |
| against_htf AND BREAKOUT | 8 | 1.0493 | 0.9321 | 0.4942 | -0.475 | -0.48 | -0.9692 | 3 | 5 | REJECT |
| against_htf AND SECONDARY_SIGNAL | 6 | 1.0493 | 1.0768 | 0.4942 | 0.6146 | 1.62 | 0.1204 | 2 | 4 | SHADOW_TEST |
| against_htf AND ASIA AND low_volume | 0 | 1.0493 | 1.0493 | 0.4942 | 0.4942 | 0.0 | 0.0 | 0 | 0 | REJECT |
| against_htf AND ASIA AND BREAKOUT | 0 | 1.0493 | 1.0493 | 0.4942 | 0.4942 | 0.0 | 0.0 | 0 | 0 | REJECT |
| against_htf AND low_volume AND BREAKOUT | 1 | 1.0493 | 1.1655 | 0.4942 | 1.4942 | 2.05 | 1.0 | 0 | 1 | WATCH |

## Recommended Next Action

Shadow-test `against_htf AND SECONDARY_SIGNAL` before any production change.
