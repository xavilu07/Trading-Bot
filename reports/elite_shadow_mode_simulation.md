# ELITE_SHADOW_MODE_SIMULATION

Generated at: 2026-06-09T18:30:59+00:00
Data path: data
Method: Simulate PROFILE_A-F over canonical closed trades after excluding bullish_sweep and against_htf+BREAKOUT production blocks.
Recommended action: KEEP_BASELINE

## Executive Summary

- Baseline after production blocks: trades=32, WR=31.25%, PF=0.7713, TotalR=-4.5446, AvgR=-0.142
- Excluded production blocks: trades=8, WR=37.5%, PF=1.3198, TotalR=0.9692, AvgR=0.1212
- Max PF profile: PROFILE_C (trades=3, WR=0.0%, PF=0.0, TotalR=-1.3953, AvgR=-0.4651, class=NO_EDGE, trade_reduction=90.625%, PF improvement=-100.0%, R improvement=69.2976%)
- Max TotalR profile: PROFILE_C (trades=3, WR=0.0%, PF=0.0, TotalR=-1.3953, AvgR=-0.4651, class=NO_EDGE, trade_reduction=90.625%, PF improvement=-100.0%, R improvement=69.2976%)
- Best PF with enough trades: none
- Worth shadow testing? NO
- Production-only elite impact: No profile has enough trades.

## Baseline

| Trades | Wins | Losses | WR | PF | Total R | Avg R |
|---:|---:|---:|---:|---:|---:|---:|
| 32 | 10 | 22 | 31.25% | 0.7713 | -4.5446 | -0.142 |

## Profile Simulation

| Profile | Factors | Trades | WR | PF | Total R | Avg R | Reduction | PF Improvement | R Improvement | Class |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| PROFILE_A | score_bucket=90+ | 4 | 0.0% | 0.0 | -2.3953 | -0.5988 | 87.5% | -100.0% | 47.2935% | NO_EDGE |
| PROFILE_B | score_bucket=90+, htf_alignment=aligned_with_htf | 4 | 0.0% | 0.0 | -2.3953 | -0.5988 | 87.5% | -100.0% | 47.2935% | NO_EDGE |
| PROFILE_C | score_bucket=90+, htf_alignment=aligned_with_htf, setup_type=SECONDARY_SIGNAL | 3 | 0.0% | 0.0 | -1.3953 | -0.4651 | 90.625% | -100.0% | 69.2976% | NO_EDGE |
| PROFILE_D | score_bucket=90+, htf_alignment=aligned_with_htf, setup_type=SECONDARY_SIGNAL, liquidity_sweep=bearish_sweep | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 100.0% | -100.0% | 100.0% | NO_EDGE |
| PROFILE_E | score_bucket=90+, htf_alignment=aligned_with_htf, setup_type=SECONDARY_SIGNAL, liquidity_sweep=bearish_sweep, session=LONDON | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 100.0% | -100.0% | 100.0% | NO_EDGE |
| PROFILE_F | score_bucket=90+, htf_alignment=aligned_with_htf, setup_type=SECONDARY_SIGNAL, liquidity_sweep=bearish_sweep, market_regime=HIGH_VOLATILITY | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 100.0% | -100.0% | 100.0% | NO_EDGE |

## Answers

- max_pf_profile: PROFILE_C (trades=3, WR=0.0%, PF=0.0, TotalR=-1.3953, AvgR=-0.4651, class=NO_EDGE, trade_reduction=90.625%, PF improvement=-100.0%, R improvement=69.2976%)
- max_total_r_profile: PROFILE_C (trades=3, WR=0.0%, PF=0.0, TotalR=-1.3953, AvgR=-0.4651, class=NO_EDGE, trade_reduction=90.625%, PF improvement=-100.0%, R improvement=69.2976%)
- best_pf_enough_trades_profile: none
- worth_shadow_testing: NO
- production_only_elite_impact: No profile has enough trades.

## Recommended Action

KEEP_BASELINE
