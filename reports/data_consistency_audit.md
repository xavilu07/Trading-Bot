# Data Consistency Audit

- Generated at: 2026-05-29T15:21:10+00:00
- Overall status: CONSISTENT

## Canonical Dataset

- Base: `data/paper_trading/trades.csv`
- Closed trades: 40
- Total R: -3.5754
- Winrate: 32.5%
- Profit factor: 0.8439
- Max drawdown: -8.9684
- Current drawdown: -4.9069

## Systems

| System | Classification | Dataset scope | Closed trades | Total R | WR | PF | Max DD | Current DD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Dashboard | CONSISTENT | canonical_trade_source | 40 | -3.5754 | 32.5% | 0.8439 | -8.9684 | -4.9069 |
| Control Center | CONSISTENT | canonical_trade_source | 40 | -3.5754 | 32.5% | 0.8439 | -8.9684 | -4.9069 |
| Intelligence Reports | CONSISTENT | outcome_intelligence_csv | 40 | -3.5754 | 32.5% | 0.8439 | -8.9684 | -4.9069 |
| Daily Reports | CONSISTENT | canonical_trade_source_today | 0 | 0 | 0.0% | 0.0 | 0.0 | 0.0 |
| Context Toxicity | CONSISTENT | canonical_trade_source | 40 | -3.5754 | 32.5% | 0.8439 | -8.9684 | -4.9069 |
| London Short Analysis | CONSISTENT | canonical_trade_source_london_short_subset | 9 | -0.416 | 22.22% | 0.9145 | -2.0 | -1.3895 |
| Backtest Runner | CONSISTENT | canonical_trade_source | 40 | -3.5754 | 32.5% | 0.8439 | -8.9684 | -4.9069 |
| Focused Shadow Validation | CONSISTENT | canonical_trade_source | 40 | -3.5754 | 32.5% | 0.8439 | -8.9684 | -4.9069 |

## Mismatch Details

### Dashboard
- Classification: CONSISTENT
- Dataset scope: `canonical_trade_source`
- Notes: Dashboard must read data/paper_trading/trades.csv through canonical_trade_source.
- Diffs:
  - closed_trades: observed=40 expected=40 delta=0.0
  - total_r: observed=-3.5754 expected=-3.5754 delta=0.0
  - winrate: observed=32.5 expected=32.5 delta=0.0
  - profit_factor: observed=0.8439 expected=0.8439 delta=0.0
  - max_drawdown: observed=-8.9684 expected=-8.9684 delta=0.0
  - current_drawdown: observed=-4.9069 expected=-4.9069 delta=0.0

### Control Center
- Classification: CONSISTENT
- Dataset scope: `canonical_trade_source`
- Notes: Control Center must read data/paper_trading/trades.csv through canonical_trade_source.
- Diffs:
  - closed_trades: observed=40 expected=40 delta=0.0
  - total_r: observed=-3.5754 expected=-3.5754 delta=0.0
  - winrate: observed=32.5 expected=32.5 delta=0.0
  - profit_factor: observed=0.8439 expected=0.8439 delta=0.0
  - max_drawdown: observed=-8.9684 expected=-8.9684 delta=0.0
  - current_drawdown: observed=-4.9069 expected=-4.9069 delta=0.0

### Intelligence Reports
- Classification: CONSISTENT
- Dataset scope: `outcome_intelligence_csv`
- Notes: Intelligence Reports are expected to align with outcome_intelligence.csv row metrics.; Manifest rows: closed_trades=40, outcome=40, edge=31, setup=24
- Diffs:
  - closed_trades: observed=40 expected=40 delta=0.0
  - total_r: observed=-3.5754 expected=-3.5754 delta=0.0
  - winrate: observed=32.5 expected=32.5 delta=0.0
  - profit_factor: observed=0.8439 expected=0.8439 delta=0.0
  - max_drawdown: observed=-8.9684 expected=-8.9684 delta=0.0
  - current_drawdown: observed=-4.9069 expected=-4.9069 delta=0.0

### Daily Reports
- Classification: CONSISTENT
- Dataset scope: `canonical_trade_source_today`
- Notes: Daily DEV Report is intentionally scoped to paper trades closed today.
- Diffs:
  - closed_trades: observed=0 expected=0 delta=0.0
  - total_r: observed=0 expected=0 delta=0.0
  - winrate: observed=0.0 expected=0.0 delta=0.0
  - profit_factor: observed=0.0 expected=0.0 delta=0.0
  - max_drawdown: observed=0.0 expected=0.0 delta=0.0
  - current_drawdown: observed=0.0 expected=0.0 delta=0.0

### Context Toxicity
- Classification: CONSISTENT
- Dataset scope: `canonical_trade_source`
- Notes: Context Toxicity must use canonical_trade_source, not strategy validation rows.
- Diffs:
  - closed_trades: observed=40 expected=40 delta=0.0
  - total_r: observed=-3.5754 expected=-3.5754 delta=0.0
  - winrate: observed=32.5 expected=32.5 delta=0.0
  - profit_factor: observed=0.8439 expected=0.8439 delta=0.0
  - max_drawdown: observed=-8.9684 expected=-8.9684 delta=0.0
  - current_drawdown: observed=-4.9069 expected=-4.9069 delta=0.0

### London Short Analysis
- Classification: CONSISTENT
- Dataset scope: `canonical_trade_source_london_short_subset`
- Notes: London Short Analysis is expected to match the LONDON+SHORT subset if it only uses canonical trades.
- Diffs:
  - closed_trades: observed=9 expected=9 delta=0.0
  - total_r: observed=-0.416 expected=-0.416 delta=0.0
  - winrate: observed=22.22 expected=22.22 delta=0.0
  - profit_factor: observed=0.9145 expected=0.9145 delta=0.0
  - max_drawdown: observed=-2.0 expected=-2.0 delta=0.0
  - current_drawdown: observed=-1.3895 expected=-1.3895 delta=0.0

### Backtest Runner
- Classification: CONSISTENT
- Dataset scope: `canonical_trade_source`
- Notes: Backtest Runner baseline should be comparable to the canonical closed-trade universe.
- Diffs:
  - closed_trades: observed=40 expected=40 delta=0.0
  - total_r: observed=-3.5754 expected=-3.5754 delta=0.0
  - winrate: observed=32.5 expected=32.5 delta=0.0
  - profit_factor: observed=0.8439 expected=0.8439 delta=0.0
  - max_drawdown: observed=-8.9684 expected=-8.9684 delta=0.0
  - current_drawdown: observed=-4.9069 expected=-4.9069 delta=0.0

### Focused Shadow Validation
- Classification: CONSISTENT
- Dataset scope: `canonical_trade_source`
- Notes: Focused shadow validation must use canonical_trade_source.
- Diffs:
  - closed_trades: observed=40 expected=40 delta=0.0
  - total_r: observed=-3.5754 expected=-3.5754 delta=0.0
  - winrate: observed=32.5 expected=32.5 delta=0.0
  - profit_factor: observed=0.8439 expected=0.8439 delta=0.0
  - max_drawdown: observed=-8.9684 expected=-8.9684 delta=0.0
  - current_drawdown: observed=-4.9069 expected=-4.9069 delta=0.0

## Source Files

- `canonical_trades`: exists=True rows=49 size=67621 bytes
- `signals_log`: exists=True rows=214 size=368878 bytes
- `outcome_intelligence`: exists=True rows=40 size=13157 bytes
- `edge_breakdown`: exists=True rows=31 size=3519 bytes
- `setup_rankings`: exists=True rows=24 size=3215 bytes

## Core Reports

- `outcome_intelligence.csv`: exists=True rows=40 size=13157 bytes
- `edge_breakdown.csv`: exists=True rows=31 size=3519 bytes
- `setup_rankings.csv`: exists=True rows=24 size=3215 bytes
