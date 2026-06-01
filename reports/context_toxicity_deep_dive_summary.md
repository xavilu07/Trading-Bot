# Context Toxicity Deep Dive

- Generated at: 2026-05-29T15:17:24+00:00
- Records analyzed: 40
- Min trades: 5
- Global WR: 32.5%
- Global Total R: -3.5754
- Global PF: 0.8439

## Confirmed Toxic Contexts

- GLOBAL | market_regime=HIGH_VOLATILITY | setup_type=SECONDARY_SIGNAL | n=5 | WR=0.0% | TotalR=-3.0308 | AvgR=-0.6062 | PF=0.0
- GLOBAL | market_regime=HIGH_VOLATILITY | rejection_reason=directional_confluence_failed | n=5 | WR=0.0% | TotalR=-3.0308 | AvgR=-0.6062 | PF=0.0
- SHORT_ONLY | SEGMENT | segment=SHORT_ONLY | n=21 | WR=14.29% | TotalR=-9.8004 | AvgR=-0.4667 | PF=0.3296

## Hidden Edge Contexts

- none

## Unstable Contexts

- GLOBAL | entry_context=CHOPPY_RANGE | setup_type=MAIN_SIGNAL | n=5 | WR=20.0% | TotalR=-3.0 | AvgR=-0.6 | PF=0.25
- GLOBAL | entry_context=CHOPPY_RANGE | score_bucket=<60 | n=5 | WR=20.0% | TotalR=-3.0 | AvgR=-0.6 | PF=0.25
- GLOBAL | market_regime=HIGH_VOLATILITY | entry_context=BREAKOUT | n=7 | WR=14.29% | TotalR=-3.0308 | AvgR=-0.433 | PF=0.2481
- GLOBAL | entry_context=CHOPPY_RANGE | target_context=entry_context=CHOPPY_RANGE | n=7 | WR=28.57% | TotalR=-3.5896 | AvgR=-0.5128 | PF=0.2821
- GLOBAL | entry_context=CHOPPY_RANGE | entry_context=CHOPPY_RANGE | n=7 | WR=28.57% | TotalR=-3.5896 | AvgR=-0.5128 | PF=0.2821
- GLOBAL | entry_context=CHOPPY_RANGE | market_regime=RANGING | n=7 | WR=28.57% | TotalR=-3.5896 | AvgR=-0.5128 | PF=0.2821
- GLOBAL | entry_context=CHOPPY_RANGE | body_ratio_bucket=UNKNOWN | n=7 | WR=28.57% | TotalR=-3.5896 | AvgR=-0.5128 | PF=0.2821
- GLOBAL | entry_context=CHOPPY_RANGE | penalty=market_structure_range_penalty:10 | n=7 | WR=28.57% | TotalR=-3.5896 | AvgR=-0.5128 | PF=0.2821
- GLOBAL | entry_context=CHOPPY_RANGE | rejection_reason=market_structure_range_penalty | n=7 | WR=28.57% | TotalR=-3.5896 | AvgR=-0.5128 | PF=0.2821
- GLOBAL | entry_context=CHOPPY_RANGE | direction=short | n=4 | WR=0.0% | TotalR=-4.0 | AvgR=-1.0 | PF=0.0

## Recommended Keep Blocked

- SHORT_ONLY | SEGMENT | segment=SHORT_ONLY | n=21 | AvgR=-0.4667 | PF=0.3296
- GLOBAL | market_regime=HIGH_VOLATILITY | setup_type=SECONDARY_SIGNAL | n=5 | AvgR=-0.6062 | PF=0.0
- GLOBAL | market_regime=HIGH_VOLATILITY | rejection_reason=directional_confluence_failed | n=5 | AvgR=-0.6062 | PF=0.0

## Watchlist

- CHOPPY_RANGE_SHORT | SEGMENT | segment=CHOPPY_RANGE_SHORT | n=4 | toxicity=48.0 | opportunity=0.0
- GLOBAL | SEGMENT | segment=GLOBAL | n=40 | toxicity=25.5301 | opportunity=6.549
- HIGH_VOLATILITY_LONG | SEGMENT | segment=HIGH_VOLATILITY_LONG | n=3 | toxicity=16.5835 | opportunity=0.0
- HIGH_VOLATILITY_SHORT | SEGMENT | segment=HIGH_VOLATILITY_SHORT | n=5 | toxicity=10.0 | opportunity=20.1028
- LONG_ONLY | SEGMENT | segment=LONG_ONLY | n=19 | toxicity=0.0 | opportunity=56.64
- LONDON_ONLY | SEGMENT | segment=LONDON_ONLY | n=14 | toxicity=0.0 | opportunity=35.2335
- CHOPPY_RANGE_LONG | SEGMENT | segment=CHOPPY_RANGE_LONG | n=3 | toxicity=0.0 | opportunity=11.8283
- GLOBAL | entry_context=CHOPPY_RANGE | setup_type=MAIN_SIGNAL | n=5 | toxicity=64.75 | opportunity=0.0
- GLOBAL | entry_context=CHOPPY_RANGE | score_bucket=<60 | n=5 | toxicity=64.75 | opportunity=0.0
- GLOBAL | market_regime=HIGH_VOLATILITY | entry_context=BREAKOUT | n=7 | toxicity=61.0957 | opportunity=0.0

## Candidate Relaxations

- no_candidate_relaxation_detected

## What NOT To Change

- do_not_relax_unknown_contexts_globally
- do_not_relax_choppy_range_or_high_volatility_without_direction_session_volume_filters
- do_not_change_public_policy_from_low_confidence_samples
