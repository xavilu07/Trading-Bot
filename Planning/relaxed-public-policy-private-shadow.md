# Relaxed Public Policy Private Shadow Signals

## Objetivo

Enviar al canal privado DEV una señal shadow cuando `relaxed_public_safety_v2` permitiría una señal que la `public_safety_policy` actual bloquea.

Esto no activa publicación pública. Es observabilidad privada para evaluar si la policy relajada merece pasar a canary real en el futuro.

## Variables

```env
RELAXED_PUBLIC_POLICY_RUNTIME_SHADOW=true
RELAXED_PUBLIC_POLICY_SEND_DEV=true
```

## Reglas

- La `public_safety_policy` actual sigue controlando el canal público.
- Si la policy actual bloquea y `relaxed_public_safety_v2` permite, se envía un mensaje adicional solo a DEV.
- Si `relaxed_public_safety_v2` bloquea, no se envía shadow.
- Si la señal ya fue enviada como shadow en el mismo proceso, se deduplica.
- Nunca envía al canal público.

## Mensaje DEV

Etiqueta obligatoria:

```text
🧪 RELAXED SHADOW SIGNAL
No publicada en canal público.
```

Incluye:

- Símbolo
- Dirección
- Entry
- Stop loss
- Take profit
- Score
- Session
- Setup type
- Entry context
- Motivo del bloqueo actual

## Logs

Eventos:

- `relaxed_public_shadow_signal_sent_dev`
- `relaxed_public_shadow_signal_skipped`

## Tracking

`data/bot_activity/signals_log.jsonl` añade:

- `relaxed_public_policy_decision`
- `relaxed_public_policy_vs_current`
- `relaxed_public_shadow_sent_dev`

## Estado

Private shadow only. No modifica estrategia, scheduler, live trading, canary público ni publicación pública.
