# Public SHORT Canary

## Objetivo

Permitir un despliegue canary extremadamente limitado de señales públicas `SHORT`, sin activar todos los shorts ni relajar filtros globales.

La lógica está diseñada para que el comportamiento actual permanezca intacto si `PUBLIC_SHORT_CANARY_ENABLED=false`.

## Contexto de Edge

Datos observados:

- `SHORT all-time`: +54.5376R, PF 1.5921
- `LONG all-time`: +2.4935R, PF 1.0171
- `LONDON_SHORT`: 65 trades, +30.9651R, PF 2.5261
- `Focused shadow LONDON_SHORT_PULLBACK_MAIN_SIGNAL`: 18 trades, +17.9584R, PF 3.5426
- `HIGH_VOLATILITY_LONG`: 100 trades, -17.6685R

## Regla Canary

Solo puede ir a público si se cumple exactamente:

```text
session = LONDON
direction = SHORT
entry_context = PULLBACK
setup_type = MAIN_SIGNAL
score >= 70
```

El resto de SHORT sigue bloqueado para canal público.

## Variables de Entorno

```bash
PUBLIC_SHORT_CANARY_ENABLED=false
PUBLIC_SHORT_CANARY_SESSION=LONDON
PUBLIC_SHORT_CANARY_DIRECTION=SHORT
PUBLIC_SHORT_CANARY_ENTRY_CONTEXT=PULLBACK
PUBLIC_SHORT_CANARY_SETUP_TYPE=MAIN_SIGNAL
PUBLIC_SHORT_CANARY_MIN_SCORE=70
```

## Integración

- Policy: `src/trading_signals/application/policies/public_canary_policy.py`
- Public safety: `src/trading_signals/application/policies/public_safety_policy.py`
- Publicación: `src/trading_signals/application/use_cases/publish_signal.py`
- Tracking JSONL: `data/bot_activity/signals_log.jsonl`

## Logs

Eventos nuevos:

```text
public_canary_evaluated
public_canary_allowed
public_canary_blocked
```

Campos relevantes:

```text
reason
symbol
score
session
entry_context
setup_type
```

## Tracking

Cada entrada en `signals_log.jsonl` puede incluir:

```json
{
  "public_canary_decision": "allow",
  "public_canary_match": true,
  "public_canary_reason": "matched"
}
```

## Restricciones

No toca:

- Estrategia base
- LONG flow
- Live trading real
- Paper trading
- Scheduler loop
- Telegram DEV
- HIGH_VOLATILITY_LONG

## Reversibilidad

Para desactivar:

```bash
PUBLIC_SHORT_CANARY_ENABLED=false
```

No requiere cambios de código.
