from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from trading_signals.agents.proposal_store import DEFAULT_PROPOSALS_PATH, update_proposal_status
from trading_signals.agents.strategy_knowledge_base import DEFAULT_KNOWLEDGE_BASE_PATH, record_proposal_review


def build_approval_payload(proposal: dict[str, Any], *, chat_id: str) -> dict[str, Any]:
    text = format_proposal_message(proposal)
    proposal_id = str(proposal["id"])
    return {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "✅ Approve", "callback_data": f"agent:approve:{proposal_id}"},
                    {"text": "❌ Reject", "callback_data": f"agent:reject:{proposal_id}"},
                    {"text": "📊 Details", "callback_data": f"agent:details:{proposal_id}"},
                ],
                [
                    {"text": "🔁 Revalidate", "callback_data": f"agent:revalidate:{proposal_id}"},
                    {"text": "🧪 Find Alternative", "callback_data": f"agent:alternative:{proposal_id}"},
                ]
            ]
        },
    }


def format_proposal_message(proposal: dict[str, Any]) -> str:
    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    conditions = context.get("conditions") or proposal.get("conditions") or [proposal.get("title")]
    rule = ", ".join(str(item) for item in conditions if item)
    baseline_pf = context.get("baseline_pf")
    baseline_total_r = context.get("baseline_total_r")
    remaining = int(proposal.get("baseline_trades") or 0) - int(proposal.get("trades_lost") or 0)
    recommendation = "Implementar con feature flag reversible." if proposal.get("edge_type") == "STRUCTURAL_EDGE" else "Revisar manualmente antes de cualquier cambio."
    return (
        "🤖 Quantum Investment Council\n\n"
        f"Decisión:\n{proposal.get('action')}\n\n"
        f"Título:\n{proposal.get('title')}\n\n"
        f"Regla:\n{rule}\n\n"
        f"Tipo:\n{proposal.get('edge_type') or context.get('edge_type')}\n\n"
        "Impacto simulado:\n"
        f"PF {baseline_pf} → {proposal.get('expected_pf')}\n"
        f"TotalR {baseline_total_r}R → {proposal.get('expected_total_r')}R\n"
        f"Trades restantes: {remaining} / {proposal.get('baseline_trades')}\n"
        f"Reducción: {proposal.get('trade_reduction_pct')}%\n\n"
        f"Riesgo:\n{proposal.get('risk_level')}\n"
        f"Motivo:\n{', '.join(str(item) for item in proposal.get('risk_objections') or []) or 'none'}\n\n"
        f"Recomendación:\n{recommendation}\n\n"
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
    no_actionable_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if proposal is None:
        if no_actionable_summary is not None:
            return send_no_actionable_summary(
                no_actionable_summary,
                bot_token=bot_token,
                chat_id=chat_id,
                dry_run=dry_run,
            )
        return [{"status": "skipped", "reason": "no_cio_proposal"}]
    return send_proposals_for_approval(
        [proposal],
        bot_token=bot_token,
        chat_id=chat_id,
        dry_run=dry_run,
        limit=1,
    )


def send_no_actionable_summary(
    summary: dict[str, Any],
    *,
    bot_token: str,
    chat_id: str,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    if not bot_token or not chat_id:
        return [{"status": "skipped", "reason": "telegram_approval_not_configured"}]
    payload = {
        "chat_id": chat_id,
        "text": format_no_actionable_message(summary),
        "reply_markup": {"inline_keyboard": []},
    }
    if dry_run:
        return [{"status": "dry_run", "proposal_id": "no_actionable", "payload": payload}]
    return [_send_payload(bot_token, payload, proposal_id="no_actionable")]


def format_no_actionable_message(summary: dict[str, Any]) -> str:
    candidates = summary.get("candidates") if isinstance(summary.get("candidates"), list) else []
    discarded = sum(1 for item in candidates if item.get("status") == "discarded")
    return (
        "🧠 Agent Committee Summary\n\n"
        "No actionable proposal.\n"
        f"Candidates reviewed: {len(candidates)}\n"
        f"Discarded: {discarded}\n\n"
        "Reason: top hypotheses were too aggressive or had no profitable variant.\n\n"
        "No se ejecutará ningún cambio automáticamente."
    )


def handle_approval_callback(
    callback_data: str,
    *,
    proposal_store_path: Path = DEFAULT_PROPOSALS_PATH,
    knowledge_base_path: Path = DEFAULT_KNOWLEDGE_BASE_PATH,
    actor: str = "telegram_dev",
    rejection_reason: str = "",
) -> dict[str, Any]:
    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "agent":
        return {"handled": False, "reason": "invalid_callback"}
    action, proposal_id = parts[1], parts[2]
    if action in {"details", "revalidate", "alternative"}:
        return {"handled": True, "action": action, "proposal_id": proposal_id, "status": "unchanged"}
    if action not in {"approve", "reject"}:
        return {"handled": False, "reason": "unsupported_action", "action": action}
    status = "approved" if action == "approve" else "rejected"
    updated = update_proposal_status(
        proposal_id,
        status,
        path=proposal_store_path,
        actor=actor,
        approval_metadata={"rejection_reason": rejection_reason} if rejection_reason else {},
    )
    knowledge_item = None
    if updated is not None:
        knowledge_item = record_proposal_review(
            updated,
            status,
            path=knowledge_base_path,
            rejection_reason=rejection_reason,
        )
    return {
        "handled": updated is not None,
        "action": action,
        "proposal_id": proposal_id,
        "status": status if updated is not None else "not_found",
        "proposal": updated,
        "knowledge_item": knowledge_item,
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
