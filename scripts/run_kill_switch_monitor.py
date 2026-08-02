from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_signals.agents.qic_telegram_config import load_qic_telegram_config
from trading_signals.agents.telegram_approval import send_qic_status_message
from trading_signals.app.settings import load_settings
from trading_signals.risk.kill_switch import evaluate_kill_switch
from trading_signals.risk.trading_pause import DEFAULT_PAUSE_PATH, is_trading_paused, pause_trading


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trip the manual trading-pause latch on kill-switch conditions.")
    parser.add_argument("--pause-path", type=Path, default=DEFAULT_PAUSE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    settings = load_settings()

    current = is_trading_paused(args.pause_path)
    if current.get("paused"):
        print(json.dumps({"status": "already_paused", "state": current}, indent=2))
        return 0

    status = evaluate_kill_switch(
        settings.data_storage_path,
        enabled=settings.kill_switch_enabled,
        max_daily_loss_r=settings.max_daily_loss_r,
        max_consecutive_losses=settings.max_consecutive_losses,
        max_weekly_drawdown_r=settings.max_weekly_drawdown_r,
        cooldown_hours=settings.kill_switch_cooldown_hours,
    )
    if not status.get("kill_switch_active"):
        print(json.dumps({"status": "healthy", "kill_switch": status}, indent=2))
        return 0

    if args.dry_run:
        print(json.dumps({"status": "would_pause", "kill_switch": status}, indent=2))
        return 0

    state = pause_trading(reason=str(status.get("kill_switch_reason") or "kill_switch_active"), details=status, path=args.pause_path)
    _notify(status)
    print(json.dumps({"status": "paused", "state": state}, indent=2))
    return 0


def _notify(status: dict[str, object]) -> None:
    config = load_qic_telegram_config()
    if not config.get("configured"):
        return
    text = (
        "🛑 INTERRUPTOR DE EMERGENCIA ACTIVADO\n\n"
        f"Motivo: {status.get('kill_switch_reason')}\n"
        f"R diario: {status.get('daily_realized_r')}\n"
        f"R semanal: {status.get('weekly_realized_r')}\n"
        f"Pérdidas consecutivas: {status.get('consecutive_losses')}\n\n"
        "Se han detenido los trades NUEVOS. Los ya abiertos siguen igual, no se ha tocado ningún código.\n"
        "Para reanudar hace falta tu aprobación manual: scripts/resume_trading.py"
    )
    for chat_id in config.get("chat_ids") or []:
        send_qic_status_message(bot_token=str(config["bot_token"]), chat_id=str(chat_id), text=text, proposal_id="kill_switch")


if __name__ == "__main__":
    raise SystemExit(main())
