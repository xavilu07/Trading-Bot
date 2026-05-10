from __future__ import annotations


def telegram_status(notifier) -> dict[str, object]:
    token_configured = bool(getattr(notifier, "bot_token", ""))
    recipients = list(getattr(notifier, "chat_ids", []) or [])
    public_chat_id = str(getattr(notifier, "public_chat_id", "") or "").strip()
    dev_chat_id = str(getattr(notifier, "dev_chat_id", "") or "").strip()
    configured_destinations = len(recipients) + int(bool(public_chat_id)) + int(bool(dev_chat_id))
    ok = token_configured and bool(recipients)
    if token_configured and (public_chat_id or dev_chat_id):
        ok = True
    return {
        "ok": ok,
        "score": 100.0 if ok else 50.0 if configured_destinations else 0.0,
        "reason": "telegram_configured" if ok else "telegram_partially_configured" if configured_destinations else "telegram_not_configured",
        "details": {
            "token_configured": token_configured,
            "configured_recipients": configured_destinations,
            "public_chat_configured": bool(public_chat_id),
            "dev_chat_configured": bool(dev_chat_id),
        },
    }


def send_public_signal(notifier, message: str, *, dry_run: bool = False) -> list[dict[str, object]]:
    if hasattr(notifier, "send_public_signal"):
        return notifier.send_public_signal(message, dry_run=dry_run)
    return notifier.publish(message, dry_run=dry_run)


def send_dev_message(notifier, message: str, *, dry_run: bool = False) -> list[dict[str, object]]:
    if hasattr(notifier, "send_dev_message"):
        return notifier.send_dev_message(message, dry_run=dry_run)
    return notifier.publish(message, dry_run=dry_run)


def send_dev_signal_detail(notifier, message: str, *, dry_run: bool = False) -> list[dict[str, object]]:
    if hasattr(notifier, "send_dev_signal_detail"):
        return notifier.send_dev_signal_detail(message, dry_run=dry_run)
    return send_dev_message(notifier, message, dry_run=dry_run)
