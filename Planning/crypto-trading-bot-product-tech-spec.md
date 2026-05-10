# Product + Tech Spec
## Sistema Profesional de Señales de Trading para Criptomonedas

## 1. Resumen Ejecutivo

### 1.1 Objetivo del producto
El producto es un motor de señales de trading para criptomonedas diseñado para analizar mercado, evaluar setups de alta calidad y emitir decisiones operativas `LONG`, `SHORT` o `NO_TRADE` con trazabilidad completa y gestión explícita de riesgo.

No debe concebirse como un simple script de alertas, sino como una base de plataforma preparada para evolucionar hacia:

- servicio backend,
- API de señales,
- producto SaaS,
- e integración futura con FIRE.

### 1.2 Propuesta de valor
La propuesta de valor no es “predecir el mercado”, sino reducir ruido, imponer disciplina y convertir reglas operativas en decisiones consistentes, auditables y escalables.

### 1.3 Público objetivo

- Traders discrecionales que quieren señales ya procesadas.
- Operadores semi-sistemáticos que quieren una capa objetiva de validación.
- Equipos de producto e ingeniería que quieren construir un motor de señales reusable.

### 1.4 Principio rector
El sistema debe priorizar:

1. robustez,
2. validación,
3. distribución,
4. sofisticación.

## 2. Visión del Producto

### 2.1 Qué es
Una aplicación de análisis multi-timeframe para criptomonedas que obtiene datos de mercado, calcula contexto técnico, filtra setups y genera señales con plan de riesgo y salida por Telegram o API.

### 2.2 Para qué sirve

- Analizar múltiples símbolos de forma sistemática.
- Evitar decisiones discrecionales inconsistentes.
- Estandarizar criterios de entrada y descarte.
- Emitir señales accionables con `SL`, `TP`, `RR` y tamaño sugerido.
- Crear histórico útil para validación, reporting y mejora continua.

### 2.3 Qué no es

- No es un predictor infalible.
- No es un sistema de copy trading en esta fase.
- No es un bot de ejecución automática desde el MVP.
- No es un producto de IA generativa.

## 3. Tesis de Producto

### 3.1 Tesis principal
Un buen producto de trading automation no gana por tener más indicadores, sino por permitir:

- probar,
- medir,
- comparar,
- desplegar,
- y revisar estrategias con disciplina.

### 3.2 Decisión estratégica
El producto debe nacer como `signal engine`, no como bot monolítico.

Eso implica:

- motor de decisión desacoplado,
- contratos estables de datos,
- riesgo modelado como entidad propia,
- canales de salida separados del análisis,
- y almacenamiento histórico como parte central del producto.

## 4. Estrategia Base

### 4.1 Setup inicial
El setup base del producto es:

`Liquidity Sweep + Multi-Timeframe Alignment + Structural Confirmation`

### 4.2 Timeframes

- Timeframe de entrada: `1h`
- Timeframe superior: `4h`

Regla operativa:

- Solo se analizarán velas cerradas.
- Nunca se debe generar señal usando una vela aún abierta del timeframe de entrada o del timeframe superior.

### 4.3 Variables analíticas mínimas

- tendencia,
- estructura de mercado,
- niveles de liquidez,
- sweep de liquidez,
- ATR,
- distancia a liquidez normalizada en ATR,
- confirmación de vela,
- setup score.

### 4.4 Condición LONG

- `trend_1h == bullish`
- `trend_4h == bullish`
- `market_structure_1h == bullish`
- `liquidity_sweep_1h == bullish_sweep`
- `setup_score >= threshold`
- `atr >= atr_min_threshold`
- `distance_to_liquidity <= max_distance_atr`
- `body_ratio >= min_body_ratio`

### 4.5 Condición SHORT

- `trend_1h == bearish`
- `trend_4h == bearish`
- `market_structure_1h == bearish`
- `liquidity_sweep_1h == bearish_sweep`
- `setup_score >= threshold`
- `atr >= atr_min_threshold`
- `distance_to_liquidity <= max_distance_atr`
- `body_ratio >= min_body_ratio`

### 4.6 Condición NO_TRADE
Se devuelve `NO_TRADE` si:

- falla cualquier filtro duro,
- no existe alineación multi-timeframe,
- la estructura es `range`,
- no existe sweep válido,
- o no hay confluencia direccional suficiente.

## 5. Lógica de Trading Detallada

### 5.1 Filtro de alineación de timeframe
Regla:

- La tendencia de `1h` debe coincidir con la de `4h`.

Objetivo:

- Evitar operar contra contexto dominante.

### 5.2 Filtro de calidad
Regla:

- `setup_score >= 60` en la versión inicial.

Objetivo:

- Exigir confluencia mínima antes de permitir evaluación final.

### 5.3 Filtro de mercado lateral
Regla:

- No operar si `market_structure == range`.

Objetivo:

- Reducir ruido y falsas rupturas.

### 5.4 Filtro de volatilidad
Regla:

- No operar si `ATR < atr_min_threshold`.

Objetivo:

- Evitar setups con rango insuficiente para justificar el riesgo.

### 5.5 Filtro de distancia a liquidez
Regla:

- No operar si `distance_to_liquidity > max_distance_atr`.

Objetivo:

- Evitar entradas extendidas y de mala relación riesgo/beneficio.

Definición formal:

- `distance_to_liquidity` se expresa siempre en múltiplos de ATR.
- Fórmula conceptual: `abs(entry_price - target_liquidity_level) / ATR`

### 5.6 Confirmación de vela
Regla:

- No operar si `body_ratio < min_body_ratio`.

Objetivo:

- Exigir intención mínima en la vela de activación.

### 5.7 Pseudológica
```text
for symbol in symbols:
  load 1h and 4h data
  validate data
  compute analysis

  if trend_1h != trend_4h:
    return NO_TRADE

  if structure == range:
    return NO_TRADE

  if atr < atr_min_threshold:
    return NO_TRADE

  if distance_to_liquidity_atr > max_distance_atr:
    return NO_TRADE

  if body_ratio < min_body_ratio:
    return NO_TRADE

  if setup_score < score_threshold:
    return NO_TRADE

  if bullish confluence:
    return LONG

  if bearish confluence:
    return SHORT

  return NO_TRADE
```

## 6. Gestión de Riesgo

### 6.1 Filosofía
La gestión de riesgo debe tratar cada señal como hipótesis operativa, no como predicción.

### 6.2 Stop loss
El `SL` debe invalidar la hipótesis del setup.

Base recomendada:

- `LONG`: por debajo de liquidez relevante menos buffer por ATR.
- `SHORT`: por encima de liquidez relevante más buffer por ATR.

Fórmula conceptual:

```text
LONG:
  stop_loss = liquidity_low - (ATR * sl_atr_multiplier)

SHORT:
  stop_loss = liquidity_high + (ATR * sl_atr_multiplier)
```

### 6.3 Take profit
El `TP` debe combinar:

- target estructural,
- y reward mínimo por política de riesgo.

Fórmula conceptual:

```text
risk = abs(entry - stop_loss)

LONG:
  minimum_2r_target = entry + (2 * risk)

SHORT:
  minimum_2r_target = entry - (2 * risk)

take_profit = best_valid_target(structural_target, minimum_2r_target, decision)
```

### 6.4 Risk/Reward
Regla mínima:

- no emitir señal válida si `RR < 2.0`, salvo configuración explícita distinta.

### 6.5 Tamaño de posición
Fórmula conceptual:

```text
risk_amount = account_equity * risk_per_trade
position_size = risk_amount / abs(entry - stop_loss)
```

### 6.6 Evolución prevista del módulo de riesgo
El modelo debe quedar preparado para soportar en futuro:

- múltiples take profits,
- breakeven,
- trailing take profit,
- trailing stop loss,
- perfiles de riesgo por usuario o preset.

## 7. Arquitectura del Sistema

### 7.1 Principios de arquitectura

- Separación entre análisis, estrategia, riesgo, persistencia y notificación.
- Dominio desacoplado de infraestructura.
- Configuración externa y versionada.
- Trazabilidad completa de decisiones.
- Preparación para API y para FIRE.
- Persistencia intercambiable sin cambiar el dominio.

### 7.2 Diagrama lógico
```text
[Scheduler / Trigger]
        |
        v
[Market Data Provider]
        |
        v
[Normalization + Validation]
        |
        v
[Analysis Engine]
        |
        v
[Strategy Engine]
        |
        +------> [Rejected Signal + rejection reasons]
        |
        v
[Risk Engine]
        |
        v
[Signal Repository]
        |
        +------> [Telegram Notifier]
        |
        +------> [API / Frontend / FIRE]
        |
        v
[Metrics / Logs / Reports]
```

### 7.3 Componentes principales

#### 7.3.1 Market Data

- Obtención de OHLCV desde Binance.
- Validación temporal y estructural.
- Normalización de tipos y timestamps.
- Exclusión explícita de velas no cerradas.
- Control de frescura de datos por símbolo y timeframe.

#### 7.3.2 Analysis Engine

- Cálculo de tendencia.
- Cálculo de estructura.
- Cálculo de niveles de liquidez.
- Detección de sweep.
- Cálculo de ATR.
- Cálculo de setup score.

#### 7.3.3 Strategy Engine

- Evaluación formal del setup.
- Registro de filtros aprobados y fallidos.
- Generación de `decision_trace`.
- Generación de `rejection_reasons`.

#### 7.3.4 Risk Engine

- Cálculo de `SL`, `TP`, `RR` y `position_size`.

#### 7.3.5 Notification System

- Formateo de mensaje.
- Publicación a Telegram.
- Registro de estado de entrega.

#### 7.3.6 Storage

- Persistencia de scans, snapshots, evaluaciones, señales, riesgos y errores.

## 8. Estructura Exacta del Proyecto

```text
trading-signals/
  pyproject.toml
  README.md
  .env.example
  migrations/
  docs/
    planning/
      crypto-trading-bot-product-tech-spec.md
  src/
    app/
      cli.py
      settings.py
      container.py
    domain/
      entities/
        market_snapshot.py
        strategy_evaluation.py
        risk_plan.py
        trade_signal.py
        scan_run.py
      value_objects/
        enums.py
      services/
        trend_service.py
        structure_service.py
        liquidity_service.py
        volatility_service.py
        candle_confirmation_service.py
        scoring_service.py
        risk_service.py
      strategies/
        base.py
        liquidity_sweep_mtf_v1.py
    application/
      use_cases/
        run_market_scan.py
        analyze_symbol.py
        publish_signal.py
        backtest_strategy.py
      dto/
        analysis_result.py
        signal_payload.py
      ports/
        market_data_port.py
        signal_repository_port.py
        scan_run_repository_port.py
        notification_port.py
        metrics_port.py
    infrastructure/
      market_data/
        binance_client.py
      notifications/
        telegram_notifier.py
      persistence/
        file_store.py
        repositories.py
        serializers.py
      logging/
        logger.py
      metrics/
        noop_metrics.py
    interfaces/
      api/
        main.py
        routes/
          health.py
          signals.py
          analysis.py
      schedulers/
        cron_runner.py
  tests/
    unit/
    integration/
    fixtures/
  scripts/
    run_scan.py
    run_backtest.py
```

## 9. Modelos de Dominio

### 9.1 Enums base

- `Trend`: `bullish`, `bearish`, `neutral`
- `MarketStructure`: `bullish`, `bearish`, `range`
- `LiquiditySweep`: `bullish_sweep`, `bearish_sweep`, `none`
- `SignalDecision`: `long`, `short`, `no_trade`
- `SignalStatus`: `pending`, `valid`, `rejected`, `published`, `failed`
- `DeliveryStatus`: `pending`, `sent`, `failed`

### 9.2 Entidad `MarketSnapshot`
Campos mínimos:

- `symbol`
- `timeframe`
- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `trend`
- `market_structure`
- `liquidity_high`
- `liquidity_low`
- `liquidity_sweep`
- `atr`
- `body_ratio`
- `distance_to_liquidity_atr`
- `setup_score`

### 9.3 Entidad `StrategyEvaluation`
Campos mínimos:

- `evaluation_id`
- `strategy_id`
- `strategy_version`
- `symbol`
- `entry_timeframe`
- `higher_timeframe`
- `entry_snapshot_id`
- `higher_snapshot_id`
- `decision`
- `decision_trace`
- `rejection_reasons`
- `passed_filters`
- `failed_filters`
- `setup_score`
- `confidence`

### 9.4 Entidad `RiskPlan`
Campos mínimos:

- `entry`
- `stop_loss`
- `take_profit`
- `risk_reward`
- `risk_amount`
- `position_size`
- `sl_method`
- `tp_method`

### 9.5 Entidad `TradeSignal`
Campos mínimos:

- `signal_id`
- `scan_run_id`
- `evaluation_id`
- `risk_plan_id`
- `strategy_id`
- `strategy_version`
- `symbol`
- `decision`
- `status`
- `entry_timeframe`
- `higher_timeframe`
- `entry_snapshot_id`
- `higher_snapshot_id`
- `created_at`

Campos expandidos opcionales para API:

- `entry_snapshot`
- `higher_snapshot`
- `evaluation`
- `risk_plan`

### 9.6 Entidad `ScanRun`
Campos mínimos:

- `scan_run_id`
- `started_at`
- `finished_at`
- `symbols_total`
- `symbols_processed`
- `signals_emitted`
- `signals_rejected`
- `errors_count`
- `status`

## 10. Contratos JSON

### 10.1 `AnalysisResult`
```json
{
  "symbol": "BTCUSDT",
  "entry_timeframe": "1h",
  "higher_timeframe": "4h",
  "entry_snapshot": {
    "timestamp": "2026-04-23T18:00:00Z",
    "trend": "bullish",
    "market_structure": "bullish",
    "liquidity_high": 69420.0,
    "liquidity_low": 68120.0,
    "liquidity_sweep": "bullish_sweep",
    "atr": 410.5,
    "body_ratio": 0.64,
    "distance_to_liquidity_atr": 0.9,
    "setup_score": 76.0
  },
  "higher_snapshot": {
    "timestamp": "2026-04-23T16:00:00Z",
    "trend": "bullish",
    "market_structure": "bullish",
    "atr": 890.2,
    "setup_score": 71.0
  }
}
```

### 10.2 `StrategyEvaluation`
```json
{
  "evaluation_id": "eval_01",
  "strategy_id": "liquidity_sweep_mtf",
  "strategy_version": "v1",
  "entry_snapshot_id": "snap_entry_01",
  "higher_snapshot_id": "snap_higher_01",
  "decision": "long",
  "setup_score": 76.0,
  "confidence": 0.78,
  "passed_filters": [
    "timeframe_alignment",
    "quality_score",
    "market_structure",
    "volatility",
    "distance_to_liquidity",
    "candle_confirmation",
    "directional_confluence"
  ],
  "failed_filters": [],
  "decision_trace": [
    "trend_1h=bullish",
    "trend_4h=bullish",
    "market_structure=bullish",
    "liquidity_sweep=bullish_sweep",
    "setup_score=76.0"
  ],
  "rejection_reasons": []
}
```

### 10.3 `TradeSignal`
```json
{
  "signal_id": "sig_01",
  "scan_run_id": "run_01",
  "evaluation_id": "eval_01",
  "risk_plan_id": "risk_01",
  "strategy_id": "liquidity_sweep_mtf",
  "strategy_version": "v1",
  "symbol": "BTCUSDT",
  "decision": "long",
  "status": "valid",
  "entry_timeframe": "1h",
  "higher_timeframe": "4h",
  "entry_snapshot_id": "snap_entry_01",
  "higher_snapshot_id": "snap_higher_01",
  "created_at": "2026-04-23T18:01:03Z",
  "risk_plan": {
    "entry": 68450.0,
    "stop_loss": 67980.0,
    "take_profit": 69390.0,
    "risk_reward": 2.0,
    "risk_amount": 10.0,
    "position_size": 0.0213
  }
}
```

### 10.4 `RejectedSignal`
```json
{
  "signal_id": "sig_02",
  "symbol": "ETHUSDT",
  "decision": "no_trade",
  "status": "rejected",
  "rejection_reasons": [
    "market_structure_range",
    "body_ratio_below_threshold"
  ],
  "setup_score": 54.0,
  "created_at": "2026-04-23T18:01:10Z"
}
```

## 11. Persistencia Actual y Modelo Futuro

### 11.1 Persistencia actual
La primera versión no utilizará SQL.

La persistencia inicial será basada en archivos estructurados en JSON o JSONL, con repositorios explícitos detrás de puertos de aplicación.

Objetivos de esta decisión:

- simplificar la primera implementación,
- reducir complejidad operativa,
- mantener trazabilidad suficiente,
- y permitir migración futura sin reescribir el dominio.

### 11.2 Requisitos obligatorios de la persistencia por archivos

- Cada entidad debe tener identificador estable.
- Los registros deben escribirse en formato serializable y versionable.
- Debe existir partición lógica por tipo de entidad y fecha.
- Debe soportar lectura por `id`, por `symbol` y por rango temporal.
- Debe poder reemplazarse por SQL sin cambiar casos de uso ni entidades.
- Las escrituras deben ser atómicas para evitar archivos corruptos.
- Debe existir mecanismo de bloqueo simple para evitar colisiones entre procesos.
- Cada archivo persistido debe incluir `schema_version`.

### 11.3 Layout recomendado de almacenamiento
```text
data/
  scan_runs/
    2026-04-23/
      run_01.json
  market_snapshots/
    2026-04-23/
      snap_entry_01.json
      snap_higher_01.json
  strategy_evaluations/
    2026-04-23/
      eval_01.json
  risk_plans/
    2026-04-23/
      risk_01.json
  trade_signals/
    2026-04-23/
      sig_01.json
  signal_deliveries/
    2026-04-23/
      delivery_01.json
  system_errors/
    2026-04-23/
      err_01.json
```

### 11.4 Reglas de persistencia por archivos

- Un archivo por entidad canónica.
- Escritura mediante archivo temporal y rename atómico.
- No reescribir una entidad publicada sin versionado o motivo explícito.
- Mantener índices auxiliares simples solo si son regenerables.
- Todo timestamp en UTC ISO 8601.
- Toda entidad persistida debe incluir:
  - `id`
  - `schema_version`
  - `created_at`
  - `updated_at` si aplica
  - `source` si proviene de proveedor externo

### 11.5 Modelo relacional futuro
Aunque no se implementará ahora, el sistema debe quedar preparado para migrar después a una base de datos. El modelo relacional objetivo incluye:

#### 11.5.1 `scan_runs`

- `id`
- `started_at`
- `finished_at`
- `status`
- `symbols_total`
- `symbols_processed`
- `signals_emitted`
- `signals_rejected`
- `errors_count`
- `created_at`

#### 11.5.2 `market_snapshots`

- `id`
- `scan_run_id`
- `symbol`
- `timeframe`
- `snapshot_timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `trend`
- `market_structure`
- `liquidity_high`
- `liquidity_low`
- `liquidity_sweep`
- `atr`
- `body_ratio`
- `distance_to_liquidity_atr`
- `setup_score`
- `created_at`

#### 11.5.3 `strategy_evaluations`

- `id`
- `scan_run_id`
- `symbol`
- `strategy_id`
- `strategy_version`
- `entry_snapshot_id`
- `higher_snapshot_id`
- `decision`
- `setup_score`
- `confidence`
- `decision_trace`
- `passed_filters`
- `failed_filters`
- `rejection_reasons`
- `created_at`

#### 11.5.4 `risk_plans`

- `id`
- `evaluation_id`
- `entry`
- `stop_loss`
- `take_profit`
- `risk_reward`
- `risk_amount`
- `position_size`
- `sl_method`
- `tp_method`
- `created_at`

#### 11.5.5 `trade_signals`

- `id`
- `scan_run_id`
- `evaluation_id`
- `risk_plan_id`
- `symbol`
- `decision`
- `status`
- `entry_timeframe`
- `higher_timeframe`
- `entry_snapshot_id`
- `higher_snapshot_id`
- `published_at`
- `created_at`

#### 11.5.6 `signal_deliveries`

- `id`
- `signal_id`
- `channel`
- `status`
- `recipient`
- `provider_message_id`
- `payload`
- `error_message`
- `attempted_at`

#### 11.5.7 `system_errors`

- `id`
- `scan_run_id`
- `symbol`
- `stage`
- `error_type`
- `error_message`
- `payload`
- `created_at`

### 11.6 Principio de migración futura
La migración a SQL deberá ser una sustitución de infraestructura, no una reescritura del dominio.

## 12. Configuración del Sistema

### 12.1 Variables mínimas

- `APP_ENV`
- `LOG_LEVEL`
- `BINANCE_BASE_URL`
- `BINANCE_MARKET_TYPE`
- `SCAN_SYMBOLS`
- `ENTRY_TIMEFRAME`
- `HIGHER_TIMEFRAME`
- `SETUP_SCORE_THRESHOLD`
- `ATR_MIN_THRESHOLD`
- `MAX_DISTANCE_TO_LIQUIDITY_ATR`
- `MIN_BODY_RATIO`
- `RISK_PER_TRADE`
- `MIN_RR`
- `ACCOUNT_BALANCE_REFERENCE`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_IDS`
- `DATA_STORAGE_PATH`

### 12.2 Principios de configuración

- Ningún secreto en el repositorio.
- Ningún umbral crítico hardcodeado.
- Toda configuración relevante versionable.
- La infraestructura futura debe poder activarse por entorno sin afectar al dominio.

### 12.3 Configuración que debe quedar congelada por ejecución
Cada `scan_run` debe persistir una copia efectiva de la configuración usada en ese ciclo.

Campos mínimos:

- `strategy_id`
- `strategy_version`
- `entry_timeframe`
- `higher_timeframe`
- `symbols`
- `setup_score_threshold`
- `atr_min_threshold`
- `max_distance_to_liquidity_atr`
- `min_body_ratio`
- `risk_per_trade`
- `min_rr`

## 13. Sistema de Señales

### 13.1 Objetivo
La señal debe ser:

- interpretable,
- accionable,
- auditable,
- y serializable para otros sistemas.

### 13.2 Campos mínimos del mensaje

- símbolo,
- timestamp,
- tipo de señal,
- timeframes,
- tendencia,
- estructura,
- sweep,
- setup score,
- entrada,
- stop loss,
- take profit,
- risk/reward,
- razón resumida.

### 13.3 Separación entre señal y canal
La señal canónica no debe contener payload específico de Telegram ni de ningún otro proveedor.

Regla:

- `TradeSignal` representa la decisión de negocio.
- `SignalDelivery` representa la distribución por canal.
- El texto de Telegram es una proyección de presentación, no la entidad principal.

### 13.4 Ejemplo de mensaje para Telegram
```text
Signal: LONG
Symbol: BTCUSDT
Timeframes: 1H / 4H
Trend Alignment: bullish / bullish
Market Structure: bullish
Liquidity Sweep: bullish
Setup Score: 78
ATR: 420.5
Entry: 68450.0
Stop Loss: 67890.0
Take Profit: 69570.0
Risk/Reward: 2.0
Reason:
- Tendencia alineada entre 1H y 4H
- Sweep bullish sobre liquidez previa
- Estructura bullish validada
- Precio dentro de distancia operable
- Vela de confirmación válida
```

## 14. MVP

### 14.1 Objetivo del MVP
Construir un primer sistema usable que produzca señales consistentes, medibles y auditables para un universo controlado de símbolos.

### 14.2 Alcance funcional del MVP

- Binance como fuente única de datos.
- Universo inicial de 5 a 15 símbolos.
- Estrategia única `liquidity_sweep_mtf_v1`.
- Timeframes fijos `1h` y `4h`.
- Decisiones `LONG`, `SHORT`, `NO_TRADE`.
- Cálculo de `SL`, `TP`, `RR` y `position_size`.
- Persistencia de análisis, señales, rechazos y errores.
- Envío a Telegram.
- Ejecución programada.

### 14.3 Alcance técnico del MVP

- Python modular.
- CLI para ejecutar scans.
- Persistencia inicial por archivos.
- Logs estructurados.
- Tests unitarios de dominio.
- Backtest offline básico.

### 14.4 Qué queda fuera del MVP

- ejecución automática en exchange,
- multi-exchange,
- machine learning,
- dashboard complejo,
- copy trading,
- marketplace de estrategias,
- integración operativa completa con FIRE.

### 14.5 Criterios de aceptación del MVP

- La salida es determinista para el mismo input.
- Cada `NO_TRADE` tiene `rejection_reasons`.
- Cada señal válida tiene `SL`, `TP`, `RR` y sizing.
- El fallo de un símbolo no rompe todo el scan.
- El sistema puede ejecutarse sin intervención manual.
- Existe histórico suficiente para auditoría.
- El sistema no usa velas abiertas para decidir.
- Cada señal puede reconstruirse con sus snapshots y configuración.

## 15. Benchmark de Producto

### 15.1 Conclusión del benchmark
Las plataformas que han tenido mejor resultado no destacan solo por estrategias, sino por capacidades de validación y control operativo.

### 15.2 Aprendizajes útiles

#### 15.2.1 3Commas
Ideas valiosas:

- gestión avanzada de `SL` y `TP`,
- trailing,
- múltiples take profits,
- separación entre señal y gestión de trade.

Aprendizaje para esta app:

- El modelo de riesgo debe quedar preparado para mayor riqueza futura.

#### 15.2.2 Cryptohopper
Ideas valiosas:

- paper trading,
- backtesting como función central,
- biblioteca de backtests.

Aprendizaje para esta app:

- La validación histórica y simulada debe ser prioridad tras el MVP.

#### 15.2.3 TradingView
Ideas valiosas:

- strategy alerts desacopladas del entorno local,
- ejecución desde servidor,
- strategy tester reproducible.

Aprendizaje para esta app:

- El motor debe vivir en infraestructura controlada y producir reportes reproducibles.

#### 15.2.4 Coinrule
Ideas valiosas:

- demo exchange,
- presets,
- estrategias configurables,
- métricas visibles por regla.

Aprendizaje para esta app:

- Deben existir presets y reporting por configuración en fases posteriores.

## 16. Funcionalidades Inspiradas que Sí Conviene Adoptar

### 16.1 Prioridad alta

- backtesting reproducible,
- paper trading,
- histórico navegable de señales,
- versionado de estrategias,
- reporting por estrategia y símbolo,
- separación total entre motor y canal de entrega.

### 16.2 Prioridad media

- múltiples take profits,
- breakeven,
- trailing take profit,
- trailing stop loss,
- webhooks.

### 16.3 Prioridad baja o tardía

- marketplace,
- copy trading,
- constructor visual no-code,
- multi-exchange desde el inicio.

## 17. Observabilidad y Métricas

### 17.1 Logs mínimos

- inicio y fin de `scan_run`,
- inicio y fin por símbolo,
- resultado de filtros,
- señal emitida o rechazo,
- envío de Telegram,
- error por etapa.

### 17.2 Métricas operativas mínimas

- `scan_runs_total`
- `scan_run_duration_seconds`
- `symbols_processed_total`
- `signals_emitted_total`
- `signals_rejected_total`
- `delivery_failures_total`
- `market_data_errors_total`

### 17.3 Métricas de negocio mínimas

- rechazos por filtro,
- señales por símbolo,
- señales por decisión,
- `RR` promedio,
- setup score promedio,
- tasa de entrega,
- win rate y expectancy en backtesting/forward testing.

### 17.4 Requisito de reproducibilidad
Toda señal válida y todo rechazo deben poder reconstruirse a partir de:

- snapshots exactos usados,
- versión de estrategia,
- configuración aplicada,
- evaluación registrada,
- y plan de riesgo generado.

## 18. Testing y Validación

### 18.1 Tests unitarios

- tendencia,
- estructura,
- liquidez,
- sweep,
- ATR,
- setup score,
- decisión `LONG`,
- decisión `SHORT`,
- decisión `NO_TRADE`,
- riesgo y sizing.

### 18.2 Tests de integración

- obtención de datos con mocks,
- análisis completo por símbolo,
- persistencia de snapshots y señales,
- publicación en Telegram con mock,
- fallo aislado por símbolo.
- persistencia concurrente segura en modo archivo.
- exclusión correcta de velas no cerradas.

### 18.3 Tests de validación de estrategia

- backtest con dataset fijo,
- replay de señales conocidas,
- comparación entre configuraciones.

## 19. API Interna Propuesta

### 19.1 Endpoints

- `GET /health`
- `POST /v1/scans/run`
- `GET /v1/scans/{scan_run_id}`
- `GET /v1/signals/latest`
- `GET /v1/signals/{signal_id}`
- `GET /v1/signals?symbol=BTCUSDT`
- `GET /v1/evaluations/{evaluation_id}`

### 19.2 Payload de análisis manual
```json
{
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "entry_timeframe": "1h",
  "higher_timeframe": "4h",
  "strategy_id": "liquidity_sweep_mtf",
  "dry_run": false
}
```

## 20. Escalabilidad

### 20.1 De motor a backend

- FastAPI para exposición de API.
- PostgreSQL para persistencia principal.
- Redis para caché, locks o colas.
- Workers asíncronos para scans masivos.

### 20.2 De backend a SaaS

- multiusuario,
- control de planes,
- cuotas,
- autenticación,
- auditoría,
- separación por tenant.

### 20.3 Topología futura dockerizada
No se implementará ahora, pero la arquitectura objetivo debe permitir esta composición:

```text
[Nginx / Traefik reverse proxy]
          |
          +--> [Frontend web]
          |
          +--> [Backend API]
                    |
                    +--> [Worker / Scheduler]
                    |
                    +--> [Database]
```

### 20.4 Requisitos para esa futura dockerización

- Backend stateless siempre que sea posible.
- Persistencia detrás de repositorios intercambiables.
- Variables de entorno como única fuente de configuración de despliegue.
- Separación clara entre frontend, backend, worker y proxy.
- Preparación para volúmenes persistentes en `data/` mientras no exista base de datos.

## 21. Integración Futura con FIRE

### 21.1 Objetivo
Convertir el sistema en proveedor de señales consumible por FIRE sin reescribir el dominio.

### 21.2 Requisitos FIRE-ready

- contratos JSON estables,
- estrategia y configuración versionadas,
- señal serializable sin depender de Telegram,
- API o servicio invocable,
- trazabilidad por `scan_run_id`, `evaluation_id` y `signal_id`,
- independencia del mecanismo de persistencia.

### 21.3 Entidades que FIRE debería consumir

- `TradeSignal`
- `StrategyEvaluation`
- `RiskPlan`
- `ScanRun`

## 22. Roadmap

### 22.1 Fase 0: Diseño

- cerrar dominio,
- cerrar contratos,
- cerrar política de riesgo,
- cerrar MVP.

### 22.2 Fase 1: Núcleo funcional

- market data,
- analysis engine,
- strategy engine,
- risk engine,
- persistencia,
- Telegram.

### 22.3 Fase 2: Validación

- backtesting,
- forward testing,
- métricas por filtro,
- revisión de falsos positivos y negativos.

### 22.4 Fase 3: Plataforma

- API interna,
- dashboard interno,
- presets,
- reporting de estrategia.

### 22.5 Fase 4: Expansión

- paper trading,
- biblioteca de backtests,
- trailing y multi-TP,
- integración más profunda con FIRE,
- monetización vía API y suscripciones.

## 23. Checklist de Implementación

### 23.1 Semana 1

- estructura del proyecto,
- settings,
- enums,
- entidades,
- puertos,
- casos de uso base.

### 23.2 Semana 2

- cliente Binance,
- servicios de análisis,
- estrategia `v1`,
- risk service.

### 23.3 Semana 3

- almacenamiento por archivos,
- repositorios,
- Telegram,
- CLI,
- logging estructurado.

### 23.4 Semana 4

- tests unitarios,
- tests de integración,
- primer backtest,
- ajuste inicial de umbrales.

### 23.5 Semana 5+

- API,
- métricas,
- dashboard,
- preparación FIRE.

## 24. Riesgos y Limitaciones

### 24.1 Riesgos de mercado

- cambios de régimen,
- barridos sin continuación,
- correlación entre activos,
- eventos exógenos que invalidan la lectura técnica.

### 24.2 Riesgos técnicos

- rate limits,
- datos incompletos,
- latencia,
- errores de notificación,
- mala calidad de histórico.

### 24.3 Riesgos de producto

- exceso de complejidad prematura,
- falta de trazabilidad,
- monetizar antes de validar,
- confiar en optimización sin baseline sólido.

## 25. Decisión Final
El producto debe construirse como un motor de señales:

- determinista,
- auditable,
- pequeño en su primera versión,
- extensible,
- desacoplado,
- y preparado para FIRE.

La decisión correcta no es meter más features cuanto antes. La decisión correcta es construir primero un núcleo serio que pueda demostrar consistencia y edge. A partir de ahí sí tiene sentido crecer hacia paper trading, analytics avanzados, API comercial e integración profunda con FIRE.

## 26. Preparación para Descomposición en Work Items

### 26.1 Regla de descomposición
Todo work item debe cumplir estas condiciones:

- tener objetivo claro,
- tener salida verificable,
- tocar una sola responsabilidad principal,
- y poder validarse con criterio de aceptación explícito.

### 26.2 Epics recomendadas

- `EPIC-01` Fundaciones de proyecto
- `EPIC-02` Market data y validación
- `EPIC-03` Analysis engine
- `EPIC-04` Strategy engine
- `EPIC-05` Risk engine
- `EPIC-06` Persistencia por archivos
- `EPIC-07` Notificaciones
- `EPIC-08` Observabilidad
- `EPIC-09` Backtesting y validación
- `EPIC-10` API interna
- `EPIC-11` Preparación FIRE

### 26.3 Plantilla de work item

- `WI-ID`
- `Título`
- `Epic`
- `Objetivo`
- `Descripción`
- `Dependencias`
- `Entradas`
- `Salidas`
- `Criterios de aceptación`
- `Riesgos`
- `Notas de implementación`

## 27. Descomposición Inicial Recomendada

### 27.1 EPIC-01 Fundaciones de proyecto

- `WI-001` Crear estructura base del repositorio
- `WI-002` Definir settings y carga de configuración
- `WI-003` Definir enums y entidades del dominio
- `WI-004` Definir puertos de aplicación

### 27.2 EPIC-02 Market data y validación

- `WI-010` Implementar cliente Binance OHLCV
- `WI-011` Implementar normalización de payloads
- `WI-012` Implementar validación de dataset
- `WI-013` Implementar exclusión de velas abiertas
- `WI-014` Implementar control de frescura de datos

### 27.3 EPIC-03 Analysis engine

- `WI-020` Implementar cálculo de tendencia
- `WI-021` Implementar cálculo de estructura
- `WI-022` Implementar cálculo de liquidez
- `WI-023` Implementar detección de sweep
- `WI-024` Implementar ATR
- `WI-025` Implementar body ratio
- `WI-026` Implementar setup score
- `WI-027` Construir `MarketSnapshot`

### 27.4 EPIC-04 Strategy engine

- `WI-030` Implementar filtros duros
- `WI-031` Implementar decisión LONG
- `WI-032` Implementar decisión SHORT
- `WI-033` Implementar decisión NO_TRADE
- `WI-034` Implementar `decision_trace`
- `WI-035` Implementar `rejection_reasons`
- `WI-036` Implementar `StrategyEvaluation`

### 27.5 EPIC-05 Risk engine

- `WI-040` Implementar cálculo de stop loss
- `WI-041` Implementar cálculo de take profit
- `WI-042` Implementar validación de RR mínimo
- `WI-043` Implementar sizing
- `WI-044` Implementar `RiskPlan`

### 27.6 EPIC-06 Persistencia por archivos

- `WI-050` Implementar serializers
- `WI-051` Implementar file store atómico
- `WI-052` Implementar locking básico
- `WI-053` Implementar repositorio de snapshots
- `WI-054` Implementar repositorio de evaluaciones
- `WI-055` Implementar repositorio de señales
- `WI-056` Implementar repositorio de errores
- `WI-057` Persistir configuración efectiva por `scan_run`

### 27.7 EPIC-07 Notificaciones

- `WI-060` Implementar formatter de Telegram
- `WI-061` Implementar cliente Telegram
- `WI-062` Implementar `SignalDelivery`
- `WI-063` Implementar modo dry-run de publicación

### 27.8 EPIC-08 Observabilidad

- `WI-070` Implementar logging estructurado
- `WI-071` Implementar métricas mínimas
- `WI-072` Implementar registro de errores por etapa

### 27.9 EPIC-09 Backtesting y validación

- `WI-080` Implementar runner de backtest
- `WI-081` Implementar fixtures de mercado
- `WI-082` Implementar reporte básico de resultados
- `WI-083` Implementar replay de señales conocidas

### 27.10 EPIC-10 API interna

- `WI-090` Implementar `/health`
- `WI-091` Implementar `POST /v1/scans/run`
- `WI-092` Implementar `GET /v1/signals/latest`
- `WI-093` Implementar `GET /v1/signals/{signal_id}`

### 27.11 EPIC-11 Preparación FIRE

- `WI-100` Consolidar contratos JSON
- `WI-101` Versionar schemas
- `WI-102` Validar compatibilidad de payloads

## 28. Criterios de Aceptación por Módulo

### 28.1 Market data

- Devuelve solo velas cerradas.
- Devuelve timestamps normalizados en UTC.
- Falla con error explícito si faltan datos críticos.

### 28.2 Analysis engine

- Produce snapshots deterministas para el mismo dataset.
- No mezcla unidades de distancia.
- Incluye todos los campos mínimos definidos.

### 28.3 Strategy engine

- Devuelve siempre una decisión válida.
- Toda decisión incluye trazabilidad suficiente.
- Todo rechazo incluye razones explícitas.

### 28.4 Risk engine

- Nunca produce ordenación inválida de precios.
- Nunca devuelve `RR` inconsistente con `entry`, `SL` y `TP`.
- Nunca produce `position_size` negativa o nula en señales válidas.

### 28.5 Persistencia

- Toda entidad se escribe de forma atómica.
- Toda entidad queda recuperable por `id`.
- Toda entidad contiene `schema_version`.

### 28.6 Notificaciones

- Un fallo de entrega no elimina la señal.
- Todo intento de entrega queda persistido.
- El formatter no modifica la señal canónica.
