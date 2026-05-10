# Sistema de Agentes

Este proyecto define agentes documentales, no procesos autónomos en producción.

Cada agente representa una responsabilidad funcional del flujo de construcción:

- `planner`: baja producto a intent y work items.
- `backend`: implementa dominio, aplicación e interfaces.
- `qa`: valida tests, contratos y criterios de aceptación.
- `ops`: prepara ejecución local y futura dockerización.

La validación de este sistema se hace comprobando:

- existencia de cada definición,
- ownership claro,
- inputs y outputs bien definidos,
- no solapamiento ambiguo de responsabilidades.
