# Trading Signals

Motor de señales para criptomonedas con:

- estrategia base `liquidity_sweep_mtf_v1`,
- persistencia por archivos,
- CLI,
- API interna,
- tests,
- y workflow `specsmd`.

## Comandos

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m trading_signals.app.cli scan --dry-run
python -m trading_signals.app.cli telegram-start --dry-run
python -m trading_signals.app.cli telegram-listener
python -m trading_signals.app.cli scheduler
uvicorn trading_signals.interfaces.api.main:app --reload
pytest
```

## Quantum Investment Council

El QIC autónomo es un control plane offline/DEV separado del scheduler de trading. Sus flags quedan apagados por defecto y no activa estrategia, live trading ni Telegram público.

```bash
PYTHONPATH=src .venv/bin/python scripts/run_qic_autonomous.py --once --dry-run
PYTHONPATH=src .venv/bin/python scripts/run_qic_autonomous.py --health
PYTHONPATH=src .venv/bin/python scripts/test_qic_end_to_end.py --dry-run
```

Arquitectura, systemd, Telegram, rollback y checklist VPS: [Planning/qic-autonomous-operations.md](Planning/qic-autonomous-operations.md).

## Telegram listener

El listener de Telegram es un proceso separado del scanner de mercado.

```bash
make telegram-listener
```

Qué hace:

- lee `getUpdates` de Telegram en bucle,
- procesa nuevos `/start`,
- guarda usuarios nuevos en `telegram_users.json`,
- guarda el último `update_id` procesado en `telegram_state.json`,
- envía la bienvenida solo una vez por usuario,
- responde mensajes normales con una respuesta automática básica,
- y no envía señales ni interfiere con el scheduler de mercado.

## Diagnóstico de NO_TRADE

Cada ejecución del scanner guarda un CSV diario con los símbolos que terminan en `NO_TRADE`.

Ruta por defecto:

```bash
./data/diagnostics/no_trade_diagnostics/YYYY-MM-DD.csv
```

Campos registrados:

- `timestamp`
- `symbol`
- `decision`
- `setup_score`
- `trend_entry_timeframe`
- `trend_higher_timeframe`
- `market_structure`
- `liquidity_sweep`
- `atr`
- `rejection_reason`

Estos diagnósticos no se mandan a Telegram. Solo sirven para auditar qué filtros están bloqueando más señales.

Para ver el resumen diario:

```bash
make diagnostics-summary
```

Opcionalmente, puedes lanzar el script para otra fecha:

```bash
python scripts/diagnostics_summary.py --date 2026-04-24
```

## Experimental outcomes scheduler

El seguimiento de señales experimentales corre separado del bot principal.

```bash
make experimental-outcomes-up
make experimental-outcomes-status
make experimental-outcomes-logs
make experimental-outcomes-down
```

Por defecto ejecuta:

```bash
python scripts/update_experimental_outcomes.py
```

cada `3600` segundos. Puedes ajustar el intervalo con:

```bash
EXPERIMENTAL_OUTCOMES_INTERVAL_SECONDS=3600 make experimental-outcomes-up
```

## Contrato canónico de observabilidad

Los lectores productivos deben usar
`trading_signals.data.canonical_trade_source` y declarar un universo:

- `accepted`: operaciones aceptadas/tradeables; es el valor por defecto para
  KPI, QIC y Edge Memory.
- `published`: vista de `accepted` limitada a publicaciones públicas
  confirmadas. La intención o un fallo de Telegram nunca cuentan.
- `rejected`: contrafactuales rechazados, disponibles solo para investigación.
- `shadow`: experimentos no productivos.
- `unknown`: clasificación histórica conservadora cuando la evidencia no basta.

Los resultados nuevos guardan `gross_result_r`, costes por componente,
`total_cost` y `net_result_r`. Los defaults conservadores, expresados en R por
operación, son comisión `0.02`, spread `0.01`, slippage `0.01` y funding `0`.
Se pueden sobrescribir con `TRADING_COMMISSION_R`, `TRADING_SPREAD_R`,
`TRADING_SLIPPAGE_R` y `TRADING_FUNDING_R`. Las filas históricas sin costes no
se recalculan ni se falsean: se leen con coste cero y `costs_known=false`.

No existe una migración destructiva. El loader normaliza en memoria los CSV
antiguos y el escritor añade las columnas nuevas cuando una operación vuelve a
guardarse. Antes de desplegar, se debe respaldar `data/`, comprobar el esquema
en una copia y conservar el CSV de producción sin reescritura masiva.

Cada scheduler adquiere el lock configurado por `SCHEDULER_LOCK_FILE` (por
defecto `.runtime/scheduler.lock`). El arranque, los heartbeats y el lock
incluyen SHA de Git, hash de configuración segura y `DEPLOYMENT_ID`, permitiendo
identificar el proceso activo y bloquear una segunda instancia.
