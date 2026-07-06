from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.proposal_store import DEFAULT_PROPOSALS_PATH, update_proposal_status
from trading_signals.agents.strategy_knowledge_base import DEFAULT_KNOWLEDGE_BASE_PATH, record_proposal_review

DEFAULT_QIC_TELEGRAM_OFFSET_PATH = Path("data") / "qic" / "telegram_update_offset.json"


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
                    {"text": "🧠 Debate", "callback_data": f"agent:debate:{proposal_id}"},
                    {"text": "🔁 Revalidate", "callback_data": f"agent:revalidate:{proposal_id}"},
                    {"text": "🧪 Find Alternative", "callback_data": f"agent:alternative:{proposal_id}"},
                ],
                [
                    {"text": "🛠 Implementation Review", "callback_data": f"agent:implementation_review:{proposal_id}"},
                    {"text": "📦 Generate Patch", "callback_data": f"agent:generate_patch:{proposal_id}"},
                    {"text": "🧪 Start Shadow", "callback_data": f"agent:start_shadow:{proposal_id}"},
                ]
            ]
        },
    }


def resolve_qic_telegram_config(settings: object) -> dict[str, Any]:
    token = (
        str(getattr(settings, "qic_telegram_bot_token", "") or "")
        or str(getattr(settings, "agent_telegram_bot_token", "") or "")
        or str(getattr(settings, "telegram_bot_token", "") or "")
    )
    chat_id = (
        str(getattr(settings, "qic_telegram_chat_id", "") or "")
        or str(getattr(settings, "agent_telegram_chat_id", "") or "")
        or str(getattr(settings, "telegram_dev_chat_id", "") or "")
    )
    enabled = _as_bool(getattr(settings, "qic_telegram_enabled", False))
    if not enabled:
        enabled = _as_bool(getattr(settings, "agent_telegram_approval_enabled", False))
    return {
        "enabled": enabled,
        "bot_token": token,
        "chat_id": chat_id,
        "send_no_actionable": _as_bool(getattr(settings, "qic_telegram_send_no_actionable", True)),
        "min_priority": str(getattr(settings, "qic_telegram_min_priority", "MEDIUM") or "MEDIUM"),
        "configured": bool(token and chat_id),
    }


def build_qic_test_payload(*, chat_id: str) -> dict[str, Any]:
    return {
        "chat_id": chat_id,
        "text": (
            "🤖 Quantum Investment Council\n\n"
            "Telegram DEV correctamente configurado.\n\n"
            "Si recibes este mensaje significa que el canal de comunicación está listo."
        ),
        "reply_markup": {"inline_keyboard": []},
    }


def send_qic_test_message(*, bot_token: str, chat_id: str, dry_run: bool = False) -> dict[str, Any]:
    if not bot_token or not chat_id:
        return {"status": "skipped", "reason": "qic_telegram_not_configured"}
    results = []
    for target_chat_id in _chat_ids(chat_id):
        payload = build_qic_test_payload(chat_id=target_chat_id)
        if dry_run:
            results.append({"status": "dry_run", "proposal_id": "qic_test", "payload": payload})
        else:
            results.append(_send_payload(bot_token, payload, proposal_id="qic_test"))
    if len(results) == 1:
        return results[0]
    if all(item.get("status") == "sent" for item in results):
        status = "sent"
    elif all(item.get("status") == "dry_run" for item in results):
        status = "dry_run"
    else:
        status = "partial"
    return {"status": status, "results": results}


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
        for target_chat_id in _chat_ids(chat_id):
            payload = build_approval_payload(proposal, chat_id=target_chat_id)
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
    results = []
    for target_chat_id in _chat_ids(chat_id):
        payload = {
            "chat_id": target_chat_id,
            "text": format_no_actionable_message(summary),
            "reply_markup": {"inline_keyboard": []},
        }
        if dry_run:
            results.append({"status": "dry_run", "proposal_id": "no_actionable", "payload": payload})
        else:
            results.append(_send_payload(bot_token, payload, proposal_id="no_actionable"))
    return results


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
    qic_output_path: Path = Path("reports") / "qic",
    actor: str = "telegram_dev",
    rejection_reason: str = "",
) -> dict[str, Any]:
    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "agent":
        return {"handled": False, "reason": "invalid_callback"}
    action, proposal_id = parts[1], parts[2]
    if action in {"details", "debate", "revalidate", "alternative", "start_shadow"}:
        return {"handled": True, "action": action, "proposal_id": proposal_id, "status": "unchanged"}
    if action == "implementation_review":
        return _handle_implementation_review_callback(
            proposal_id,
            proposal_store_path=proposal_store_path,
            knowledge_base_path=knowledge_base_path,
            qic_output_path=qic_output_path,
        )
    if action == "generate_patch":
        return _handle_generate_patch_callback(
            proposal_id,
            proposal_store_path=proposal_store_path,
            knowledge_base_path=knowledge_base_path,
            qic_output_path=qic_output_path,
        )
    if action not in {"approve", "reject"}:
        return {"handled": False, "reason": "unsupported_action", "action": action}
    status = "approved_for_implementation_review" if action == "approve" else "rejected"
    updated = update_proposal_status(
        proposal_id,
        status,
        path=proposal_store_path,
        actor=actor,
        approval_metadata={"human_approved": action == "approve", "rejection_reason": rejection_reason} if rejection_reason or action == "approve" else {},
    )
    knowledge_item = None
    if updated is not None:
        knowledge_item = record_proposal_review(
            updated,
            "approved" if action == "approve" else "rejected",
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


def _handle_implementation_review_callback(
    proposal_id: str,
    *,
    proposal_store_path: Path,
    knowledge_base_path: Path,
    qic_output_path: Path,
) -> dict[str, Any]:
    from trading_signals.agents.implementation.implementation_review_council import run_implementation_review_for_proposal_id

    review = run_implementation_review_for_proposal_id(
        proposal_id,
        proposal_store_path=proposal_store_path,
        knowledge_base_path=knowledge_base_path,
        output_path=qic_output_path,
    )
    return {
        "handled": True,
        "action": "implementation_review",
        "proposal_id": proposal_id,
        "status": "review_generated",
        "implementation_review": {
            "decision": review.get("decision"),
            "allowed_to_generate_patch": review.get("allowed_to_generate_patch"),
            "blockers": review.get("blockers", []),
        },
    }


def _handle_generate_patch_callback(
    proposal_id: str,
    *,
    proposal_store_path: Path,
    knowledge_base_path: Path,
    qic_output_path: Path,
) -> dict[str, Any]:
    from trading_signals.agents.implementation.implementation_review_council import run_implementation_review_for_proposal_id
    from trading_signals.agents.implementation.patch_generator import generate_patch_report

    review = run_implementation_review_for_proposal_id(
        proposal_id,
        proposal_store_path=proposal_store_path,
        knowledge_base_path=knowledge_base_path,
        output_path=qic_output_path,
    )
    if not review.get("allowed_to_generate_patch"):
        return {
            "handled": True,
            "action": "generate_patch",
            "proposal_id": proposal_id,
            "status": "blocked",
            "reason": "implementation_review_not_allowed",
            "implementation_review": review,
        }
    patch = generate_patch_report(review, output_path=qic_output_path, apply_patch=False)
    return {
        "handled": True,
        "action": "generate_patch",
        "proposal_id": proposal_id,
        "status": "patch_report_generated",
        "patch": {"status": patch.get("status"), "patch_applied": patch.get("patch_applied")},
    }


def process_approval_update(
    update: dict[str, Any],
    *,
    proposal_store_path: Path = DEFAULT_PROPOSALS_PATH,
    knowledge_base_path: Path = DEFAULT_KNOWLEDGE_BASE_PATH,
    qic_output_path: Path = Path("reports") / "qic",
) -> dict[str, Any]:
    callback = update.get("callback_query") if isinstance(update.get("callback_query"), dict) else {}
    data = str(callback.get("data") or "")
    actor = str((callback.get("from") or {}).get("id") or "telegram_dev")
    if not data:
        return {"handled": False, "reason": "missing_callback_data", "update_id": update.get("update_id")}
    result = handle_approval_callback(
        data,
        proposal_store_path=proposal_store_path,
        knowledge_base_path=knowledge_base_path,
        qic_output_path=qic_output_path,
        actor=actor,
    )
    result["update_id"] = update.get("update_id")
    result["callback_query_id"] = callback.get("id")
    return result


def poll_approval_callbacks(
    *,
    bot_token: str,
    proposal_store_path: Path = DEFAULT_PROPOSALS_PATH,
    knowledge_base_path: Path = DEFAULT_KNOWLEDGE_BASE_PATH,
    qic_output_path: Path = Path("reports") / "qic",
    offset_path: Path = DEFAULT_QIC_TELEGRAM_OFFSET_PATH,
    limit: int = 20,
    timeout: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not bot_token:
        return {"status": "skipped", "reason": "qic_telegram_bot_token_missing", "processed": []}
    offset = _load_update_offset(offset_path)
    updates_result = _get_updates(bot_token=bot_token, offset=offset, limit=limit, timeout=timeout, dry_run=dry_run)
    updates = updates_result.get("updates") if isinstance(updates_result.get("updates"), list) else []
    processed = []
    max_update_id = offset - 1 if offset else -1
    for update in updates:
        if not isinstance(update, dict):
            continue
        result = process_approval_update(
            update,
            proposal_store_path=proposal_store_path,
            knowledge_base_path=knowledge_base_path,
            qic_output_path=qic_output_path,
        )
        processed.append(result)
        try:
            max_update_id = max(max_update_id, int(update.get("update_id")))
        except (TypeError, ValueError):
            pass
        callback_query_id = result.get("callback_query_id")
        if callback_query_id and not dry_run:
            _answer_callback_query(bot_token, str(callback_query_id), result)
    if max_update_id >= 0 and not dry_run:
        _save_update_offset(offset_path, max_update_id + 1)
    return {
        "status": updates_result.get("status", "ok"),
        "offset": offset,
        "next_offset": max_update_id + 1 if max_update_id >= 0 else offset,
        "processed": processed,
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


def _get_updates(*, bot_token: str, offset: int, limit: int, timeout: int, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"status": "dry_run", "updates": []}
    query = urllib.parse.urlencode(
        {
            "offset": offset,
            "limit": limit,
            "timeout": timeout,
            "allowed_updates": json.dumps(["callback_query"]),
        }
    )
    req = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/getUpdates?{query}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=max(timeout + 10, 15)) as response:  # pragma: no cover - network path
            body = json.loads(response.read().decode("utf-8"))
        return {"status": "ok", "updates": body.get("result", []) if body.get("ok") else [], "raw": body}
    except Exception as exc:  # pragma: no cover - network path
        return {"status": "failed", "updates": [], "error_message": str(exc)}


def _answer_callback_query(bot_token: str, callback_query_id: str, result: dict[str, Any]) -> None:
    text = "QIC actualizado." if result.get("handled") else f"QIC: {result.get('reason', 'not handled')}"
    encoded = urllib.parse.urlencode({"callback_query_id": callback_query_id, "text": text[:180]}).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery", data=encoded, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10):  # pragma: no cover - network path
            pass
    except Exception:
        pass


def _load_update_offset(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return int(raw.get("next_offset") or 0)
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0


def _save_update_offset(path: Path, next_offset: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"next_offset": next_offset, "updated_at": datetime.now(tz=UTC).isoformat()}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _chat_ids(chat_id: str) -> list[str]:
    return [item.strip() for item in str(chat_id).split(",") if item.strip()]
