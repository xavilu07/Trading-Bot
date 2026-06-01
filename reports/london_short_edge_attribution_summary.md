# London Short Edge Attribution

- Generated at: 2026-05-29T15:17:24+00:00
- Sample size: 9
- Closed trades: 9
- Allowed / blocked rows: 9 / 0
- WR: 22.22%
- Total R: -0.416
- Avg R: -0.0462
- PF: 0.9145
- Confidence: LOW

## Top Positive Drivers

- sin datos

## Top Negative Drivers

- body_bucket=UNKNOWN | n=9 | WR=22.22% | TotalR=-0.416 | AvgR=-0.0462 | PF=0.9145
- has_penalties=true | n=9 | WR=22.22% | TotalR=-0.416 | AvgR=-0.0462 | PF=0.9145
- score_bucket=<70 | n=5 | WR=20.0% | TotalR=-0.5265 | AvgR=-0.1053 | PF=0.8486
- rr_bucket=rr_1_5_to_2 | n=5 | WR=20.0% | TotalR=-0.367 | AvgR=-0.0734 | PF=0.8034
- has_secondary_setup_requirements_failed=true | n=5 | WR=20.0% | TotalR=-0.367 | AvgR=-0.0734 | PF=0.8034
- rejection_reason=secondary_setup_requirements_failed | n=5 | WR=20.0% | TotalR=-0.367 | AvgR=-0.0734 | PF=0.8034
- setup_type=SECONDARY_SIGNAL | n=6 | WR=16.67% | TotalR=-1.367 | AvgR=-0.2278 | PF=0.5232
- entry_context=BREAKOUT | n=6 | WR=16.67% | TotalR=-1.367 | AvgR=-0.2278 | PF=0.5232

## Recommended Rules

- avoid_or_keep_private: body_bucket=UNKNOWN (n=9, WR=22.22%, AvgR=-0.0462, PF=0.9145)
- avoid_or_keep_private: has_penalties=true (n=9, WR=22.22%, AvgR=-0.0462, PF=0.9145)
- avoid_or_keep_private: score_bucket=<70 (n=5, WR=20.0%, AvgR=-0.1053, PF=0.8486)
- avoid_or_keep_private: rr_bucket=rr_1_5_to_2 (n=5, WR=20.0%, AvgR=-0.0734, PF=0.8034)
- avoid_or_keep_private: has_secondary_setup_requirements_failed=true (n=5, WR=20.0%, AvgR=-0.0734, PF=0.8034)

## What NOT To Change

- do_not_enable_all_shorts_globally
- do_not_change_public_policy_from_london_short_edge_without_context_filter
- do_not_assume_market_structure_range_penalty_is_the_root_cause
