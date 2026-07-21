# QIC Autonomous Operations V1

## Scope and safety

QIC is an offline/DEV control plane. It does not start the trading scheduler, enable live trading, alter public Telegram, write `.env`, restart services, deploy, push, or merge code. The autonomous path reuses the existing committee, learning loop, revalidation engine, implementation council, Code Engineer, proposal store, research memory, decision ledger, and strategy knowledge base.

Safe defaults:

```text
QIC_AUTONOMOUS_ENABLED=false
QIC_AUTONOMOUS_DRY_RUN=true
QIC_TELEGRAM_ENABLED=false
QIC_CODE_ENGINEER_ENABLED=false
QIC_CODE_ENGINEER_ALLOW_APPLY=false
QIC_AUTO_APPLY_ON_APPROVAL=false
QIC_AUTO_APPLY_LOW_RISK=false
QIC_AUTO_APPLY_MEDIUM_RISK=false
QIC_LIVE_TRADING_CHANGES_ALLOWED=false
QIC_API_ACTIONS_ENABLED=false
QIC_ENABLED_AGENTS=research_director,strategy_director,risk_director,simulation_director
```

Persistent Telegram credentials continue to load from `config/qic_telegram.json`, but credentials alone do not activate autonomous outbound notifications. The listener can use the persistent configuration when its systemd service is explicitly started. Tokens are never returned by the API or written to QIC reports.

## Architecture

```text
paper/market data
  -> qic_event_detector
  -> existing Research/Strategy/Risk/Simulation debate
  -> hypothesis ranking and variant search
  -> CIO proposal and proposal dedupe
  -> decision ledger, research memory, strategy knowledge base
  -> revalidation, learning loop, agent self-evaluation
  -> implementation review and Code Engineer dry-run
  -> guarded change ledger / optional low-risk apply
  -> health, state of council, daily/weekly reports
  -> centralized notification center
```

`scripts/run_qic_autonomous.py` is the canonical orchestrator. `scripts/run_qic_scheduler.py` remains as a backward-compatible wrapper and delegates to the same orchestrator.

Runtime separation:

- Configuration: existing `Settings`, `.env`, and `config/qic_telegram.json`.
- Mutable state: `data/qic/` and `data/agent_proposals/`.
- Structured logs: `logs/qic_*.jsonl`.
- Generated reports: `reports/qic/`.
- Change snapshots: `data/qic/change_backups/`.
- Maintenance backups: `data/qic_backups/`.

JSON state uses atomic replace and `.last_good` recovery. QIC process locks live under `data/qic/locks/`.

## Autonomous score

The deterministic score is capped at 100:

- Trading scheduler health: 15.
- Telegram listener health: 15.
- QIC cycle freshness: 15.
- Four active council agents in the last 24 hours: 15.
- Research memory updated: 10.
- State/revalidation report freshness: 10.
- Proposal history present: 5.
- JSON integrity: 10.
- Error budget: 5.

Missing optional observability is `UNKNOWN`, not silently healthy. Agent states are `ACTIVE`, `INACTIVE`, `DEGRADED`, `FAILING`, or `NO_DATA`.

## CLI

```bash
PYTHONPATH=src .venv/bin/python scripts/run_qic_autonomous.py --once --dry-run
PYTHONPATH=src .venv/bin/python scripts/run_qic_autonomous.py --once --phase research --dry-run
PYTHONPATH=src .venv/bin/python scripts/run_qic_autonomous.py --status
PYTHONPATH=src .venv/bin/python scripts/run_qic_autonomous.py --health
PYTHONPATH=src .venv/bin/python scripts/run_qic_autonomous.py --health --notify
PYTHONPATH=src .venv/bin/python scripts/test_qic_end_to_end.py --dry-run
```

Code-change inspection:

```bash
PYTHONPATH=src .venv/bin/python scripts/qic_code_changes.py list
PYTHONPATH=src .venv/bin/python scripts/qic_code_changes.py show CHANGE_ID
PYTHONPATH=src .venv/bin/python scripts/qic_code_changes.py verify CHANGE_ID
PYTHONPATH=src .venv/bin/python scripts/qic_code_changes.py apply CHANGE_ID --human-approved
PYTHONPATH=src .venv/bin/python scripts/qic_code_changes.py rollback CHANGE_ID --human-approved
```

`apply` validates risk, paths, limits, tests, static checks, council approval, coverage status, and rollback availability. `rollback` refuses to overwrite files changed after the QIC apply.

## Risk policy

- LOW: docs, tests, observability, formatting, internal non-functional frontend/reporting scripts.
- MEDIUM: agent behavior, memory, research/shadow scoring, notifications.
- HIGH: strategy rules, execution use cases, public behavior, deployment-sensitive code.
- EXTREME: secrets, credentials, wallets, destructive or live-trading scopes.

LOW can auto-apply only when `QIC_AUTO_APPLY_LOW_RISK=true` and every guard passes. MEDIUM requires its separate flag and remains off by default. HIGH and EXTREME always require a human and are never auto-applied. The default denylist covers `.env`, secret config, credentials, wallets, keys, live trading, risk plans, and position sizing.

## Telegram listener

The listener loads authorized DEV chat IDs from the existing persistent loader, long-polls with an offset, deduplicates callback IDs, uses a process lock, backs off on errors, and writes `reports/qic/telegram_listener.{json,md}`.

Supported commands:

```text
/status /health /qic /research /proposals /pending /history
/performance /agents /memory /edges /errors /help
```

Callbacks validate the chat, persist actor/time/callback ID, append the decision ledger, and are idempotent. Approval changes state only by default; the guarded worker described below is queued only when all three explicit auto-apply flags are enabled. API mutations remain disabled because the current dashboard has no secure admin authentication.

### Auto-apply after Telegram approval

Telegram `Approve` only queues automatic implementation when all three flags are true:

```text
QIC_AUTO_APPLY_ON_APPROVAL=true
QIC_CODE_ENGINEER_ENABLED=true
QIC_CODE_ENGINEER_ALLOW_APPLY=true
```

The default remains disabled. The callback first persists human approval, then writes a job under `data/qic/approval_jobs/` and starts `scripts/run_qic_approval_worker.py` without blocking the listener. The worker takes a per-proposal lock and runs Implementation Review, patch report generation, Code Engineer sandbox tests, guarded apply through `CodeChangeManager`, post-apply tests, and automatic rollback plus revalidation on failure. Proposal state becomes `implemented` only after a successful apply and post-apply validation.

Per-proposal reports and worker logs are written to `reports/qic/approval_pipeline_<proposal_id>.{json,md,log}`. A blocked or rolled-back pipeline leaves the proposal at `approved_for_implementation_review`. Disable any of the three flags and restart only the QIC Telegram listener to stop new automatic jobs; running jobs retain the safety checks and rollback behavior of Code Engineer V1.

## Systemd units

The repository includes:

- `qic-telegram-listener.service` (persistent listener).
- `qic-autonomous.timer` (six-hour council cycle).
- `qic-events.timer` (hourly event detector).
- `qic-revalidation.timer` (daily revalidation).
- `qic-health.timer` (five-minute health check).
- `qic-daily-report.timer` (09:00 Europe/Madrid).
- `qic-weekly-report.timer` (Monday 09:15 Europe/Madrid).
- `qic-maintenance.timer` (daily backup/rotation).

Install without enabling or starting:

```bash
sudo QIC_APP_DIR=/root/bot ./scripts/install_qic_services.sh
./scripts/status_qic_services.sh
```

Enable for future boots only after review:

```bash
sudo QIC_APP_DIR=/root/bot ./scripts/install_qic_services.sh --enable
```

Start explicitly after review:

```bash
sudo systemctl start qic-telegram-listener.service
sudo systemctl start qic-autonomous.timer qic-events.timer qic-revalidation.timer qic-health.timer
sudo systemctl start qic-daily-report.timer qic-weekly-report.timer qic-maintenance.timer
```

Uninstall while preserving data/configuration:

```bash
sudo ./scripts/uninstall_qic_services.sh
```

## Dashboard and API

The existing FastAPI/static dashboard stack was extended rather than replaced. The QIC Control Center reads:

```text
GET /api/qic/control-center
GET /api/qic/status
GET /api/qic/health
GET /api/qic/agents
GET /api/qic/proposals
GET /api/qic/memory
GET /api/qic/performance
GET /api/qic/events
GET /api/qic/changes
GET /api/qic/runs
```

Mutation routes exist only as disabled placeholders and return `503` until secure admin authentication is implemented. No token or secret is exposed.

## Health and troubleshooting

```bash
PYTHONPATH=src .venv/bin/python scripts/run_qic_autonomous.py --health
cat reports/qic/system_health.json | python3 -m json.tool
cat reports/qic/telegram_listener.json | python3 -m json.tool
systemctl status qic-telegram-listener.service
systemctl list-timers 'qic-*'
journalctl -u qic-telegram-listener.service -n 100 --no-pager
journalctl -u qic-autonomous.service -n 100 --no-pager
```

If a JSON file is corrupt, readers fall back to its `.last_good` copy where available. Do not delete locks manually until the PID and lock age have been checked. The maintenance command supports a no-change preview:

```bash
PYTHONPATH=src .venv/bin/python scripts/maintain_qic_runtime.py --dry-run
```

## VPS rollout checklist

1. `cd /root/bot && git status --short` and preserve any VPS-only edits.
2. Create an external backup of `/root/bot/data`, `/root/bot/config`, and `/root/bot/reports`.
3. Pull using the repository's reviewed deployment process; do not overwrite `.env` or `config/qic_telegram.json`.
4. Install dependencies with the existing virtualenv workflow.
5. Run `MPLBACKEND=Agg .venv/bin/pytest -q`.
6. Run `python3 -m compileall -q src scripts` and `bash -n scripts/*qic*.sh`.
7. Run `systemd-analyze verify deploy/systemd/qic-*.service deploy/systemd/qic-*.timer`.
8. Run `PYTHONPATH=src .venv/bin/python scripts/test_qic_end_to_end.py --dry-run`.
9. Run `PYTHONPATH=src .venv/bin/python scripts/run_qic_autonomous.py --once --dry-run`.
10. Verify `reports/qic/autonomous_run.json`, `state_of_council.json`, `system_health.json`, and agent activity.
11. Test Telegram configuration with `PYTHONPATH=src .venv/bin/python scripts/test_qic_telegram.py --dry-run` first, then the real test only after operator approval.
12. Install units with `scripts/install_qic_services.sh`; confirm that none were enabled or started automatically.
13. Start only the listener and health timer; verify authorized callbacks, offset persistence, and no public Telegram traffic.
14. Start event/revalidation/report timers.
15. Keep `QIC_AUTONOMOUS_DRY_RUN=true`, then start `qic-autonomous.timer`.
16. Review at least one full cycle, Research Memory growth, Decision Ledger records, agent activity, and dashboard state.
17. Enable Code Engineer only if implementation-review reports are valid; keep apply flags off.
18. Enable low-risk auto-apply only after backup/rollback verification. Never enable live-trading changes through QIC.

## Verification checklist

- Listener: report is fresh, `running=true`, callback offset advances, duplicate callback is ignored.
- QIC: autonomous run has a unique `run_id`, all selected stages, duration, input fingerprint, and no unexpected errors.
- Agents: execution totals and 24h/7d windows advance after a real council cycle.
- Memory: `research_memory.json`, knowledge base, and decision ledger update without duplicate normalized rules.
- Dashboard: `/api/qic/control-center` returns no secrets and the Control Center renders.
- Auto-apply: a sandbox LOW-risk fixture passes; MEDIUM/HIGH/EXTREME remain blocked.
- Rollback: verification succeeds and post-apply drift prevents unsafe rollback.
