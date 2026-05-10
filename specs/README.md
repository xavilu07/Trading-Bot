# specsmd

Este repositorio usa un flujo `specsmd` compatible con editores tipo Cursor o Windsurf basado en Markdown plano y rutas estables.

## Estructura

```text
specs/
  README.md
  intents/
  work-items/
  agents/
  decisions/
```

## Reglas

1. Cada `intent` agrupa un objetivo de producto o de ingeniería.
2. Cada `work-item` pertenece a un `intent` y tiene criterios de aceptación.
3. Cada `agent` define responsabilidades y límites.
4. Cada cambio relevante de arquitectura debe reflejarse en `decisions/`.

## Flujo

1. Definir intent.
2. Desglosar work items.
3. Implementar por lotes pequeños.
4. Añadir tests por work item.
5. Validar con `scripts/check_specs.py`.
