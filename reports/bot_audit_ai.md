# BOT_AUDIT_AI

- Generated at: 2026-05-30T15:11:09+00:00
- Dataset: `data/paper_trading/trades.csv`

## 1. Executive Summary

- Current state: DEFENSIVE
- Risk level: HIGH
- Confidence level: MEDIUM
- Diagnosis: 40 closed trades, totalR=-3.5754, PF=0.8439. Winning experiments detected: 1.

## 2. What Improved

- SHADOW_SEND_CURRENT_REJECT: n=14 totalR=7.3887 PF=2.6548 | Recommendation: Validated positive edge.
- SHADOW_SEND_CURRENT_REJECT: Current rejects that relaxed shadow would send: totalR=7.3887 PF=2.6548 | Recommendation: Experiment improved historical R.
- HIGH_VOLATILITY_SHORT: n=5 totalR=0.9202 PF=1.4531 | Recommendation: Promising but needs more sample.

## 3. What Worsened

- SHORT_ONLY: SHORT_ONLY: totalR=-9.8004 PF=0.3296 | Recommendation: Keep blocked or isolate in shadow.
- CONTEXT_CHOPPY_RANGE: n=7 totalR=-3.5896 PF=0.2821 | Recommendation: Keep blocked or isolate in shadow.
- SECONDARY_SIGNAL: SECONDARY_SIGNAL: totalR=-3.0308 PF=0.0 | Recommendation: Keep blocked or isolate in shadow.
- directional_confluence_failed: directional_confluence_failed: totalR=-3.0308 PF=0.0 | Recommendation: Keep blocked or isolate in shadow.
- LONDON_SHORT: n=9 totalR=-0.416 PF=0.9145 | Recommendation: Keep blocked or isolate in shadow.
- CONTEXT_HIGH_VOLATILITY: n=8 totalR=-0.0798 PF=0.9802 | Recommendation: Keep blocked or isolate in shadow.

## 4. Edge Detection

### CONFIRMED_EDGE
- SHADOW_SEND_CURRENT_REJECT | n=14 totalR=7.3887 PF=2.6548 | source=post_consistency_edge

### POSSIBLE_EDGE
- HIGH_VOLATILITY_SHORT | n=5 totalR=0.9202 PF=1.4531 | source=post_consistency_edge

### NO_EDGE
- LONG_ONLY | LONG_ONLY: totalR=6.225 PF=1.7513 | source=context_toxicity.unstable_contexts
- MAIN_SIGNAL | MAIN_SIGNAL: totalR=3.951 PF=None | source=context_toxicity.unstable_contexts
- market_structure_range_penalty:10 | market_structure_range_penalty:10: totalR=3.5615 PF=10.1438 | source=context_toxicity.unstable_contexts
- market_structure_range_penalty | market_structure_range_penalty: totalR=3.5615 PF=10.1438 | source=context_toxicity.unstable_contexts
- LONDON_ONLY | LONDON_ONLY: totalR=3.084 PF=1.5257 | source=context_toxicity.unstable_contexts
- MAIN_SIGNAL | MAIN_SIGNAL: totalR=2.951 PF=3.951 | source=context_toxicity.unstable_contexts
- PULLBACK | PULLBACK: totalR=2.951 PF=None | source=context_toxicity.unstable_contexts
- near_resistance | near_resistance: totalR=2.951 PF=None | source=context_toxicity.unstable_contexts
- <60 | <60: totalR=2.951 PF=None | source=context_toxicity.unstable_contexts
- 8 | 8: totalR=2.951 PF=None | source=context_toxicity.unstable_contexts

### TOXIC_CONTEXT
- SHORT_ONLY | SHORT_ONLY: totalR=-9.8004 PF=0.3296 | source=context_toxicity.confirmed_toxic_contexts
- CONTEXT_CHOPPY_RANGE | n=7 totalR=-3.5896 PF=0.2821 | source=post_consistency_edge
- SECONDARY_SIGNAL | SECONDARY_SIGNAL: totalR=-3.0308 PF=0.0 | source=context_toxicity.confirmed_toxic_contexts
- directional_confluence_failed | directional_confluence_failed: totalR=-3.0308 PF=0.0 | source=context_toxicity.confirmed_toxic_contexts
- LONDON_SHORT | n=9 totalR=-0.416 PF=0.9145 | source=post_consistency_edge
- CONTEXT_HIGH_VOLATILITY | n=8 totalR=-0.0798 PF=0.9802 | source=post_consistency_edge

## 5. Experiment Tracking

### Winning experiments
- SHADOW_SEND_CURRENT_REJECT | Current rejects that relaxed shadow would send: totalR=7.3887 PF=2.6548 | PF=2.6548

### Losing experiments
- none

## 6. Rejection Analysis

- edge_activation_requires_overlap_session: totalR=4.9122 | class=SAFE_TO_RELAX | n=8
- breakout_bad_location: totalR=4.4365 | class=SAFE_TO_RELAX | n=5
- against_htf: totalR=2.7377 | class=SAFE_TO_RELAX | n=7
- market_regime_ranging: totalR=2.5985 | class=SAFE_TO_RELAX | n=7
- edge_activation_requires_trending: totalR=2.419 | class=SAFE_TO_RELAX | n=8
- setup_type_secondary_signal: totalR=2.1267 | class=SAFE_TO_RELAX | n=5
- edge_activation_secondary_signal: totalR=2.1267 | class=SAFE_TO_RELAX | n=5
- entry_context_choppy_range: totalR=1.4104 | class=NEED_MORE_DATA | n=2
- low_volume: totalR=1.4104 | class=NEED_MORE_DATA | n=2
- dirty_sideways_market: totalR=1.4104 | class=NEED_MORE_DATA | n=2

## Relaxation Shadow Status

- trades captured: 0
- skips captured: 0
- last skip reason: none
- top unsafe filters: none
- top safe filters: none
- whether V1 is too strict: False
- recommendation: keep

## 7. Recommended Actions

### HIGH IMPACT
- Keep production defensive: PF is below 1.0 on canonical trades. Next: Do not relax public policy globally.
- Keep blocked: SHORT_ONLY: SHORT_ONLY: totalR=-9.8004 PF=0.3296 Next: Do not promote this context.
- Keep blocked: CONTEXT_CHOPPY_RANGE: n=7 totalR=-3.5896 PF=0.2821 Next: Do not promote this context.
- Keep blocked: SECONDARY_SIGNAL: SECONDARY_SIGNAL: totalR=-3.0308 PF=0.0 Next: Do not promote this context.

### MEDIUM IMPACT
- Forward-test: SHADOW_SEND_CURRENT_REJECT: Current rejects that relaxed shadow would send: totalR=7.3887 PF=2.6548 Next: Track in shadow before promotion.
- Review rejection: edge_activation_requires_overlap_session: Destroyed 4.9122R in shadow analysis. Next: Keep DEV-only until sample increases.
- Review rejection: breakout_bad_location: Destroyed 4.4365R in shadow analysis. Next: Keep DEV-only until sample increases.
- Review rejection: against_htf: Destroyed 2.7377R in shadow analysis. Next: Keep DEV-only until sample increases.

### LOW IMPACT
- Regenerate intelligence reports daily: Audit depends on fresh reports. Next: Run report generation before the audit.

## 8. Tomorrow Priorities

1. Keep production defensive
2. Keep blocked: SHORT_ONLY
3. Keep blocked: CONTEXT_CHOPPY_RANGE
