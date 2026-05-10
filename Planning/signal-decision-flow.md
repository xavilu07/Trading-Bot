# Flujo SignalDecision

## Estado actual

`LiquiditySweepMTFV1` sigue siendo el motor real de estrategia. Su salida principal continúa siendo `StrategyEvaluation`.

`StrategyEvaluation` se mantiene por compatibilidad y auditoría:

- persistencia de evaluaciones
- lifecycle de señales
- diagnósticos legacy
- tests existentes de estrategia

Después de evaluar la estrategia real, `run_market_scan` adapta `StrategyEvaluation` a `SignalDecision`.

## Contrato operativo

`SignalDecision` es el contrato interno normalizado para:

- publicación de señales
- creación de candidatos de paper trading
- creación de candidatos de live tracking
- logging operativo y comparaciones current/parallel/shadow

El `decision_engine` paralelo no está activado como motor real. Sus decisiones siguen siendo diagnósticas.

## Flujo actual

```text
market data
  -> analyze_symbol
  -> LiquiditySweepMTFV1
  -> StrategyEvaluation
  -> SignalDecision
  -> publish / paper tracking / live tracking
```

## Dependencias legacy intencionadas

`StrategyEvaluation` sigue siendo necesario en:

- `domain/strategies/liquidity_sweep_mtf_v1.py`
- `domain/strategies/base.py`
- `application/ports/scan_run_repository_port.py`
- `infrastructure/persistence/repositories.py`
- lifecycle de señales mientras dependa de filtros legacy
- tests de compatibilidad

## Limpieza futura

Antes de activar otro motor real, se puede preparar:

- lifecycle basado en `SignalDecision`
- persistencia opcional de `SignalDecision`
- eliminación de DTOs legacy no usados
- migración de tests operativos para comparar contratos, no implementación interna
