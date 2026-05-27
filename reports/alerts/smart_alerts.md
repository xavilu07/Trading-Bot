# Smart Alerts

Generated: 2026-05-27T16:44:23.706Z
BOT_DATA_DIR: /Users/xaviestruch/Documents/Prueba Trading
Alerts: 1

## CRITICAL - Scheduler heartbeat stale
- ID: scheduler_stale
- Message: Heartbeat antiguo: 13164 minutos.
- Recommended action: Comprobar PM2, logs del scheduler y escritura de data/runtime/scheduler_heartbeat.json.
- Created at: 2026-05-27T16:44:23.706Z
- Metrics: {"last_cycle_finished_at":"2026-05-18T13:20:19.634648+00:00","heartbeat_timestamp":"2026-05-18T13:20:19.634648+00:00","age_minutes":13164,"status":"ok","cycle_number":5,"threshold_minutes":30,"stale_reason":"age_exceeds_threshold"}

## Warnings
- Missing optional file: reports/controlled_experiments_report.json
- Missing optional file: reports/london_short_focused_shadow.json
- Missing optional file: reports/london_short_analysis.json
