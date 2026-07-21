from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from trading_signals.agents.qic_runtime import append_jsonl, atomic_write_json, read_json_safe, utc_now


EVENT_PRIORITIES = {
    "QIC_STARTED": "INFO",
    "QIC_COMPLETED": "INFO",
    "QIC_FAILED": "CRITICAL",
    "NEW_RESEARCH_HYPOTHESIS": "INFO",
    "HYPOTHESIS_REJECTED": "INFO",
    "HYPOTHESIS_PROMOTED": "WARNING",
    "NEW_EDGE_CANDIDATE": "WARNING",
    "EDGE_CONFIRMED": "WARNING",
    "EDGE_DEGRADED": "CRITICAL",
    "NEW_CIO_PROPOSAL": "WARNING",
    "PROPOSAL_BLOCKED_BY_RISK": "WARNING",
    "PROPOSAL_PENDING_APPROVAL": "WARNING",
    "PROPOSAL_APPROVED": "WARNING",
    "PROPOSAL_REJECTED": "INFO",
    "CODE_GENERATED": "WARNING",
    "CODE_VALIDATION_FAILED": "CRITICAL",
    "CODE_READY_TO_APPLY": "WARNING",
    "CODE_AUTO_APPLIED": "CRITICAL",
    "CODE_APPLIED": "CRITICAL",
    "CODE_ROLLED_BACK": "CRITICAL",
    "TESTS_FAILED": "CRITICAL",
    "PERFORMANCE_IMPROVED": "INFO",
    "PERFORMANCE_DEGRADED": "CRITICAL",
    "DRAWDOWN_WARNING": "CRITICAL",
    "SCHEDULER_DOWN": "CRITICAL",
    "TELEGRAM_LISTENER_DOWN": "CRITICAL",
    "DISK_WARNING": "WARNING",
    "MEMORY_WARNING": "WARNING",
    "DAILY_SUMMARY": "INFO",
    "WEEKLY_SUMMARY": "INFO",
}
PRIORITY_RANK = {"INFO": 1, "WARNING": 2, "CRITICAL": 3}


class QICNotificationCenter:
    def __init__(
        self,
        *,
        data_path: Path = Path("data") / "qic",
        bot_token: str = "",
        chat_ids: list[str] | None = None,
        enabled: bool = False,
        dry_run: bool = False,
        cooldown_seconds: int = 900,
        rate_limit_per_hour: int = 20,
        sender: Callable[[str, str, str, dict[str, Any] | None], dict[str, Any]] | None = None,
    ) -> None:
        self.data_path = data_path
        self.bot_token = bot_token
        self.chat_ids = [str(item) for item in (chat_ids or []) if str(item)]
        self.enabled = enabled
        self.dry_run = dry_run
        self.cooldown_seconds = max(0, cooldown_seconds)
        self.rate_limit_per_hour = max(1, rate_limit_per_hour)
        self.sender = sender or _telegram_sender
        self.history_path = data_path / "notification_history.jsonl"
        self.state_path = data_path / "notification_state.json"

    def publish(
        self,
        event_type: str,
        *,
        title: str,
        message: str,
        priority: str | None = None,
        context: dict[str, Any] | None = None,
        buttons: list[list[dict[str, str]]] | None = None,
        dedupe_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_priority = str(priority or EVENT_PRIORITIES.get(event_type, "INFO")).upper()
        now = datetime.now(tz=UTC)
        fingerprint = dedupe_key or _fingerprint(event_type, title, context or {})
        state = read_json_safe(self.state_path, {"sent": {}, "hourly": [], "groups": {}})
        if not isinstance(state, dict):
            state = {"sent": {}, "hourly": [], "groups": {}}
        previous = _parse_dt((state.get("sent") or {}).get(fingerprint))
        event = {
            "event_id": f"notification_{hashlib.sha1(f'{fingerprint}|{utc_now()}'.encode()).hexdigest()[:14]}",
            "event_type": event_type,
            "priority": normalized_priority,
            "title": title,
            "message": message,
            "context": context or {},
            "dedupe_key": fingerprint,
            "created_at": now.isoformat(),
            "delivery": [],
        }
        if previous and (now - previous).total_seconds() < self.cooldown_seconds:
            groups = state.setdefault("groups", {})
            group = groups.setdefault(fingerprint, {"count": 0, "first_at": now.isoformat()})
            group["count"] = int(group.get("count") or 0) + 1
            group["last_at"] = now.isoformat()
            event.update({"status": "suppressed", "reason": "cooldown", "grouped_repetitions": group["count"]})
            atomic_write_json(self.state_path, state)
            append_jsonl(self.history_path, event)
            return event
        hourly = [_parse_dt(item) for item in state.get("hourly") or []]
        hourly = [item for item in hourly if item and item >= now - timedelta(hours=1)]
        if len(hourly) >= self.rate_limit_per_hour and normalized_priority != "CRITICAL":
            event.update({"status": "suppressed", "reason": "rate_limit"})
            append_jsonl(self.history_path, event)
            return event
        grouped = (state.get("groups") or {}).pop(fingerprint, None)
        if isinstance(grouped, dict) and int(grouped.get("count") or 0) > 0:
            event["grouped_repetitions"] = int(grouped["count"])
            event["grouped_since"] = grouped.get("first_at")
        if not self.enabled or not self.bot_token or not self.chat_ids:
            event.update({"status": "recorded", "reason": "telegram_disabled_or_unconfigured"})
        elif self.dry_run:
            event.update({"status": "dry_run", "delivery": [{"chat_id": item, "status": "dry_run"} for item in self.chat_ids]})
        else:
            markup = {"inline_keyboard": buttons or []}
            delivery = [self.sender(self.bot_token, chat_id, format_event_message(event), markup) for chat_id in self.chat_ids]
            event.update({"status": "sent" if all(item.get("status") == "sent" for item in delivery) else "partial", "delivery": delivery})
        state.setdefault("sent", {})[fingerprint] = now.isoformat()
        hourly.append(now)
        state["hourly"] = [item.isoformat() for item in hourly]
        state["updated_at"] = now.isoformat()
        atomic_write_json(self.state_path, state)
        append_jsonl(self.history_path, event)
        return event


def format_event_message(event: dict[str, Any]) -> str:
    icon = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}.get(str(event.get("priority")), "ℹ️")
    grouped = f"\nGrouped repetitions: {event.get('grouped_repetitions')}" if event.get("grouped_repetitions") else ""
    return (
        f"{icon} Quantum Investment Council\n\n"
        f"{event.get('title')}\n\n"
        f"{event.get('message')}\n\n"
        f"Event: {event.get('event_type')}{grouped}"
    )[:3900]


def read_notification_history(path: Path = Path("data") / "qic" / "notification_history.jsonl", *, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    output = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, limit):]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            output.append(item)
    return output


def _telegram_sender(bot_token: str, chat_id: str, text: str, reply_markup: dict[str, Any] | None) -> dict[str, Any]:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # pragma: no cover - network
            body = json.loads(response.read().decode("utf-8"))
        return {"status": "sent" if body.get("ok") else "failed", "chat_id": chat_id, "message_id": (body.get("result") or {}).get("message_id")}
    except Exception as exc:  # pragma: no cover - network
        return {"status": "failed", "chat_id": chat_id, "error": str(exc)}


def _fingerprint(event_type: str, title: str, context: dict[str, Any]) -> str:
    stable = json.dumps({"type": event_type, "title": title, "context": context}, sort_keys=True, default=str)
    return hashlib.sha1(stable.encode("utf-8")).hexdigest()


def _parse_dt(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
