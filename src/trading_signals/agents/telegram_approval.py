from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from trading_signals.agents.proposal_store import DEFAULT_PROPOSALS_PATH, update_proposal_status


def build_approval_payload(proposal: dict[str, Any], *, chat_id: str) -> dict[str, Any]:
    text = format_proposal_message(proposal)
    proposal_id = str(proposal["id"])
    return {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "APPROVE", "callback_data": f"agent:approve:{proposal_id}"},
                    {"text": "REJECT", "callback_data": f"agent:reject:{proposal_id}"},
                    {"text": "DETAILS", "callback_data": f"agent:details:{proposal_id}"},
                ]
            ]
        },
    }


def format_proposal_message(proposal: dict[str, Any]) -> str:
    return (
        "🧠 Agent Committee Proposal\n\n"
        f"ID: {proposal.get('id')}\n"
        f"Title: {proposal.get('title')}\n"
        f"Confidence: {proposal.get('confidence')} | Risk: {proposal.get('risk_level')}\n"
        f"Expected PF: {proposal.get('expected_pf')}\n"
        f"Expected Total R: {proposal.get('expected_total_r')}\n"
        f"Trades lost: {proposal.get('trades_lost')} | Evidence: {proposal.get('evidence')}\n\n"
        f"Hypothesis: {proposal.get('hypothesis')}\n\n"
        "No se ejecutará ningún cambio automáticamente."
    )


def send_proposals_for_approval(
    proposals: list[dict[str, Any]],
    *,
    bot_token: str,
    chat_id: str,
    dry_run: bool = False,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not bot_token or not chat_id:
        return [{"status": "skipped", "reason": "telegram_approval_not_configured"}]
    results = []
    for proposal in proposals[:limit]:
        payload = build_approval_payload(proposal, chat_id=chat_id)
        if dry_run:
            results.append({"status": "dry_run", "proposal_id": proposal["id"], "payload": payload})
            continue
        results.append(_send_payload(bot_token, payload, proposal_id=str(proposal["id"])))
    return results


def send_cio_proposal_for_approval(
    proposal: dict[str, Any] | None,
    *,
    bot_token: str,
    chat_id: str,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    if proposal is None:
        return [{"status": "skipped", "reason": "no_cio_proposal"}]
    return send_proposals_for_approval(
        [proposal],
        bot_token=bot_token,
        chat_id=chat_id,
        dry_run=dry_run,
        limit=1,
    )


def handle_approval_callback(
    callback_data: str,
    *,
    proposal_store_path: Path = DEFAULT_PROPOSALS_PATH,
    actor: str = "telegram_dev",
) -> dict[str, Any]:
    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "agent":
        return {"handled": False, "reason": "invalid_callback"}
    action, proposal_id = parts[1], parts[2]
    if action == "details":
        return {"handled": True, "action": "details", "proposal_id": proposal_id, "status": "unchanged"}
    if action not in {"approve", "reject"}:
        return {"handled": False, "reason": "unsupported_action", "action": action}
    status = "approved" if action == "approve" else "rejected"
    updated = update_proposal_status(proposal_id, status, path=proposal_store_path, actor=actor)
    return {
        "handled": updated is not None,
        "action": action,
        "proposal_id": proposal_id,
        "status": status if updated is not None else "not_found",
        "proposal": updated,
    }


def _send_payload(bot_token: str, payload: dict[str, Any], *, proposal_id: str) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(
        {
            "chat_id": payload["chat_id"],
            "text": payload["text"],
            "reply_markup": json.dumps(payload["reply_markup"]),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=encoded,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:  # pragma: no cover - network path
            body = json.loads(response.read().decode("utf-8"))
        return {
            "status": "sent",
            "proposal_id": proposal_id,
            "provider_message_id": str(body.get("result", {}).get("message_id", "")),
        }
    except Exception as exc:  # pragma: no cover - network path
        return {"status": "failed", "proposal_id": proposal_id, "error_message": str(exc)}
