# Intelligence Report WEEKLY 2026-22

Generated: 2026-05-27T16:19:17.946Z
BOT_DATA_DIR: /Users/xaviestruch/Documents/Prueba Trading

## A) Executive Summary
- Estado general: heartbeat sin datos suficientes; all-time -4.5754R, WR 32.61%, PF 0.8299
- Cambios importantes: Periodo 2026-22: 0 trades cerrados, 0R. / focused shadow sin datos
- Riesgo actual: DD actual 6.9942R
- Recomendacion principal: No tocar produccion: mantener la validacion en observabilidad/shadow hasta tener muestra suficiente.

## B) Performance
- Periodo: trades 0, cerrados 0, WR 0%, total R 0, avg R 0, PF 0, max DD 0R, DD actual 0R
- All-time: trades 56, cerrados 46, WR 32.61%, total R -4.5754, avg R -0.0995, PF 0.8299, max DD 8.4942R, DD actual 6.9942R

## C) Best/Worst Contexts
### Top setups
- sin datos suficientes
### Bottom setups
- sin datos suficientes
### Sesiones
- Win: group: LONDON | closed_trades: 14 | winrate: 42.86 | total_r: 3.084 | profit_factor: 1.5257
- Win: group: ASIA | closed_trades: 1 | winrate: 100 | total_r: 1 | profit_factor: N/A
- Loss: group: NEW_YORK | closed_trades: 14 | winrate: 21.43 | total_r: -8.4083 | profit_factor: 0.2356
- Loss: group: OVERLAP | closed_trades: 17 | winrate: 29.41 | total_r: -0.2511 | profit_factor: 0.975
### Direction LONG/SHORT
- group: LONG | closed_trades: 24 | winrate: 50 | total_r: 6.225 | profit_factor: 1.5516
- group: SHORT | closed_trades: 22 | winrate: 13.64 | total_r: -10.8004 | profit_factor: 0.3085

## D) Rejection Analysis
- group: rejected | trades: 4 | winrate: N/A | total_r: N/A | avg_r: N/A
- High score rejects >=70: 4

## E) Controlled Experiments
- sin datos suficientes

## F) Focused Shadow Validation
- sin datos suficientes

## G) Operational Health
- Scheduler/heartbeat: sin datos suficientes, age N/Am
- Last trade: 2026-05-18T13:20:17.362Z
- Last signal: 2026-05-27T14:42:20.180Z
- Binance/market data warning: N/A
- Telegram DEV: not_configured

## H) Decision Recommendations
- No tocar produccion: mantener la validacion en observabilidad/shadow hasta tener muestra suficiente.
- Sin trades cerrados en la ventana: usar el reporte como health check, no como decision de edge.
- Riesgo elevado: revisar drawdown antes de activar experimentos nuevos.
- Focused shadow con muestra insuficiente: esperar 30-50 observaciones antes de decidir.
- Resolver warnings de datos antes de usar este reporte como base de decision.

## Warnings
- Missing optional file: reports/controlled_experiments_report.json
- Missing optional file: reports/london_short_analysis.json
- Missing optional file: reports/london_short_focused_shadow.json

## Relaxation Shadow Status

- trades captured: 0
- skips captured: 0
- last skip reason: none
- top unsafe filters: none
- top safe filters: none
- whether V1 is too strict: False
- recommendation: keep
