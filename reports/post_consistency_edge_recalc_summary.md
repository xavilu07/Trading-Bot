# Post-Consistency Edge Recalculation

- Generated at: 2026-05-29T15:26:06+00:00
- Dataset: `data/paper_trading/trades.csv`
- Records analyzed: 40
- Min trades: 5
- Canonical Total R: -3.5754
- Canonical WR: 32.5%
- Canonical PF: 0.8439

## Hypotheses

| Hypothesis | Classification | n | Total R | WR | AvgR | PF | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| LONDON_SHORT | TOXIC_CONTEXT | 9 | -0.416 | 22.22% | -0.0462 | 0.9145 | London short edge after canonical consistency. |
| HIGH_VOLATILITY_LONG | NO_EDGE | 3 | -1.0 | 33.33% | -0.3333 | 0.5 | Checks whether high-volatility long remains toxic or has edge. |
| HIGH_VOLATILITY_SHORT | POSSIBLE_EDGE | 5 | 0.9202 | 20.0% | 0.184 | 1.4531 | Checks whether high-volatility short has hidden edge after canonical consistency. |
| CONTEXT_CHOPPY_RANGE | TOXIC_CONTEXT | 7 | -3.5896 | 28.57% | -0.5128 | 0.2821 | Context Toxicity target: entry_context=CHOPPY_RANGE. |
| CONTEXT_HIGH_VOLATILITY | TOXIC_CONTEXT | 8 | -0.0798 | 25.0% | -0.01 | 0.9802 | Context Toxicity target: market_regime=HIGH_VOLATILITY. |
| CONTEXT_SETUP_UNKNOWN | NO_EDGE | 0 | 0 | 0.0% | 0.0 | 0.0 | Context Toxicity target: setup_type=UNKNOWN. |
| CONTEXT_SESSION_UNKNOWN | NO_EDGE | 0 | 0 | 0.0% | 0.0 | 0.0 | Context Toxicity target: session=UNKNOWN. |
| CONTEXT_TRADE_LOCATION_UNKNOWN | NO_EDGE | 0 | 0 | 0.0% | 0.0 | 0.0 | Context Toxicity target: trade_location=UNKNOWN. |
| SHADOW_SEND_CURRENT_REJECT | CONFIRMED_EDGE | 14 | 7.3887 | 57.14% | 0.5278 | 2.6548 | Relaxed shadow policy allowed while current public policy rejected, evaluated only on canonical trades. |
| CHOPPY_RANGE_SHORT | NO_EDGE | 4 | -4.0 | 0.0% | -1.0 | 0.0 | Focused context breakdown. |
| CHOPPY_RANGE_LONG | NO_EDGE | 3 | 0.4104 | 66.67% | 0.1368 | 1.4104 | Focused context breakdown. |
| LONDON_SHORT_PULLBACK_MAIN_SIGNAL | NO_EDGE | 2 | 1.951 | 50.0% | 0.9755 | 2.951 | Focused context breakdown. |

## Surviving Hypotheses

- LONDON_SHORT: TOXIC_CONTEXT | n=9 | TotalR=-0.416 | PF=0.9145
- HIGH_VOLATILITY_SHORT: POSSIBLE_EDGE | n=5 | TotalR=0.9202 | PF=1.4531
- CONTEXT_CHOPPY_RANGE: TOXIC_CONTEXT | n=7 | TotalR=-3.5896 | PF=0.2821
- CONTEXT_HIGH_VOLATILITY: TOXIC_CONTEXT | n=8 | TotalR=-0.0798 | PF=0.9802
- SHADOW_SEND_CURRENT_REJECT: CONFIRMED_EDGE | n=14 | TotalR=7.3887 | PF=2.6548

## Interpretation

- CONFIRMED_EDGE: muestra suficiente y edge positivo claro.
- POSSIBLE_EDGE: edge positivo, pero con muestra limitada o señal estadística moderada.
- NO_EDGE: no hay evidencia positiva suficiente.
- TOXIC_CONTEXT: rendimiento negativo con muestra mínima suficiente.
