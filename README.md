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
