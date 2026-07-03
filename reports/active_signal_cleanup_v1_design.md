# ACTIVE_SIGNAL_CLEANUP_V1 Design

Purpose: close active zombie signal records without deleting historical files.

Default safety:
- `ACTIVE_SIGNAL_CLEANUP_ENABLED=false`
- `ACTIVE_SIGNAL_CLEANUP_DRY_RUN=true`
- Manual script only; not integrated into scheduler.

Zombie criteria:
- `status` is `published` or `active`
- has `published_at` or `created_at`
- no `expires_at`
- no `closed_at`
- no `close_reason` / `exit_reason`
- age greater than configured zombie hours

Apply behavior:
- creates backup under `data/trade_signals_backups/active_cleanup_v1/<timestamp>/`
- updates JSON in place with `status=closed`
- sets `lifecycle_status=expired_zombie`
- sets `close_reason=cleanup_zombie_expired`
- sets `closed_at` and `cleanup_version=ACTIVE_SIGNAL_CLEANUP_V1`

Non-goals:
- does not publish duplicates
- does not delete historical files
- does not change filters
- does not touch Telegram public routing
