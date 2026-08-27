# Roadmap: hacia la rentabilidad real

Generado 2026-08-02 tras arreglar el pipeline de trading, unificar Telegram, generalizar el
motor de código de QIC, activar auto-apply, construir la reconciliación real y el kill switch
manual. Este documento recoge qué priorizar a continuación, combinando lo que ya sabemos del
propio bot con lo que hacen los sistemas sistemáticos que sí llegan a ser rentables.

## Ya resuelto en esta ronda (no repetir)

- Scheduler de escaneo en systemd con auto-restart (antes corría en `screen`, sin vigilancia).
- Telegram unificado a una sola fuente de verdad para token/chat, con las 3 flags de
  auto-apply activadas y commit de git automático tras cada cambio aplicado.
- Generador de código de QIC generalizado a cualquier combinación de `exclude:campo=valor`
  sobre la lista seria de campos (`research/simulator.py`), no solo el filtro HTF original.
- Reconciliación real: `scripts/run_qic_reconciliation.py` (diario) compara cada propuesta de
  QIC contra `data/paper_trading/trades.csv` de verdad, no contra su propio backtest.
- Kill switch manual: `data/runtime/trading_paused.json`, revisado cada 5 min, pausa trades
  **nuevos** (nunca los abiertos) y exige `scripts/resume_trading.py` para reanudar.

## Hallazgo que debería guiar la próxima hipótesis

Al reconciliar contra datos reales: los trades que resuelven por barrera (SL/TP directo)
tienen PF 0.29-0.49 y winrate 11-16%; los que expiran por tiempo sin tocar ninguna barrera
tienen PF 2.8-3.1 y winrate 55-56%. Esto se repite en las dos propuestas ya reconciliadas.
Antes de buscar edges nuevos, vale la pena investigar **por qué el stop/TP a 24 velas
funciona tan mal comparado con dejar correr la operación** — distancia del stop vs
volatilidad real (ATR), asimetría del RR, o si el horizonte de 24 velas es demasiado corto
para el timeframe 1h/4h de la estrategia.

## Prioridad alta (barato, impacto directo en si el número de R es real)

1. **Modelado de costes siempre activo.** Ya existe el esquema (`commission`, `spread`,
   `slippage`, `funding`, `net_result_r`) y ya se aplica en cycles nuevos (visto en el
   heartbeat: `trading_commission_r: 0.02` etc.), pero solo 134 de 1622 filas históricas lo
   tienen poblado. No hace falta backfill histórico, pero confirmar que **todo trade nuevo**
   lo lleva — si no, el PF reportado seguirá siendo optimista.
2. **Validación out-of-sample antes de Telegram.** Ahora mismo cualquier propuesta que QIC
   manda a aprobación se basa en backtest interno sobre el mismo dataset que la generó. Antes
   de que una propuesta llegue a Telegram, que reserve una ventana temporal reciente (p.ej.
   las últimas 2-3 semanas) que no haya usado en la búsqueda, y reporte el resultado ahí. Es
   la defensa estándar contra overfitting que usan Freqtrade y la comunidad quant, y ataca
   directamente el patrón "evidence=586 de backtest, nunca visto en real" que encontramos al
   principio de esta sesión.
3. **Tamaño mínimo de muestra real antes de "implementable".** `research_memory.json` ya
   trackea `times_seen`/evidence — usarlo como gate explícito (p.ej. no pasar de "candidate" a
   propuesta enviable hasta 100+ trades reales relacionados, no solo evidencia de backtest).

## Prioridad media (una vez haya más muestra acumulada)

4. **Seguir la pista barrera-vs-expiración** (ver arriba) como primera hipótesis real que pase
   por el generador de código ya ampliado — con la reconciliación diaria ya construida, dentro
   de 1-2 semanas habrá suficiente muestra nueva para confirmarlo con más confianza.
5. **Consolidar los tres sistemas de "gating" de riesgo que hay hoy en paralelo**:
   `risk/kill_switch.py` (cooldown automático, bloquea solo señales públicas),
   `risk/protection_engine.py` (max_drawdown_guard, toxic_context_guard — todo en
   `shadow_only`, nunca aplicado) y el nuevo `risk/trading_pause.py` (manual, bloquea trades
   nuevos). Los tres calculan cosas parecidas de forma independiente; vale la pena revisar si
   `protection_engine.py` debería pasar de shadow a real, o si se puede fusionar con el kill
   switch para no mantener tres lógicas de riesgo separadas.
6. **IDs de propuesta inestables.** Cada vez que QIC regenera una hipótesis obtiene un
   `proposal_id` nuevo (`cio_htf_against` en `research_memory.json` vs `cio_5909920e9f22` en
   `proposals.jsonl` para la misma condición) — dificulta cruzar histórico entre sistemas. El
   `item_id` de `research_memory` (basado en las condiciones normalizadas) sí es estable y
   sería mejor clave de referencia por defecto.

## Prioridad baja / cosmético (no bloquea nada funcional)

7. **`implementation_reviews.jsonl`** (1.2MB, cientos de entradas) no bloquea nada real
   (`load_implementation_records` no tiene ningún llamador) — o se conecta de verdad como
   gate, o se deja de generar para no pagar llamadas de agentes que nadie consulta.
8. **`patch_generator.py`** genera siempre el mismo texto de diff de ejemplo (el del filtro
   HTF original) independientemente de la propuesta real — inofensivo porque solo es texto
   descriptivo en el reporte, pero confunde si alguien lo lee esperando ver el diff real.

## Ideas de fondo, con más trabajo por delante

- **Kelly/position sizing una vez haya un edge probado** — hoy el riesgo por trade es fijo
  (`risk_per_trade: 0.01` visto en la config del scheduler); no tiene sentido dimensionar por
  convicción hasta que la reconciliación confirme un edge real y estable.
- **Ensemble/multi-estrategia** en vez de una sola familia de filtros sobre
  `liquidity_sweep_mtf` — los sistemas que citan los bots rentables analizados suelen combinar
  varias señales no correlacionadas en vez de optimizar una sola una y otra vez.
- Recordatorio de la investigación externa: la sofisticación no es el edge (ver "Methods
  Matter: A Trading Agent with No Intelligence Routinely Outperforms AI-Based Traders",
  arxiv 2011.14346) — cada idea de esta lista debe demostrarse con la reconciliación real
  antes de sumar más capas de agentes.
