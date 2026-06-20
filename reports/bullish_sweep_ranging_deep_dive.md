# BULLISH_SWEEP_RANGING_DEEP_DIVE

Generated at: 2026-06-08T14:37:39+00:00
Data path: data
Method: Analyze canonical closed trades where bullish_sweep is present and market_regime=RANGING.
Classification: NOISE

## Executive Summary

- Current baseline: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- Bullish sweep + RANGING: trades=0, WR=0.0%, PF=0.0, TotalR=0.0, AvgR=0.0
- Is bullish_sweep + ranging globally toxic? NO
- Main loss subgroup: none
- Survivor subgroup: none
- Material PF improvement if removed? NO
- Future shadow filter evidence: NO

## Toxic Bullish Sweep Ranging Subgroups

Criteria: minimum 3 trades, negative Total R, PF < 1.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Survivors

Criteria: minimum 3 trades, PF > 1.1, positive Total R.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Counterfactual Removal

- PF current: 0.8439
- PF without bullish_sweep_ranging: 0.8439
- TotalR current: -3.5754
- TotalR without bullish_sweep_ranging: -3.5754
- Winrate delta: 0.0
- Trades removed: 0

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Score Bucket

| By Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

### By Rejection Reason

| By Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Recommended Action

KEEP
