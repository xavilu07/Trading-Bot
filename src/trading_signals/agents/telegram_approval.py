from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.proposal_store import DEFAULT_PROPOSALS_PATH, update_proposal_status
from trading_signals.agents.qic_telegram_config import load_qic_telegram_config
from trading_signals.agents.qic_runtime import append_jsonl, atomic_write_json, read_json_safe, utc_now
from trading_signals.agents.strategy_knowledge_base import DEFAULT_KNOWLEDGE_BASE_PATH, record_proposal_review

DEFAULT_QIC_TELEGRAM_OFFSET_PATH = Path("data") / "qic" / "telegram_update_offset.json"
DEFAULT_QIC_CALLBACK_HISTORY_PATH = Path("data") / "qic" / "telegram_callbacks.jsonl"


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
                    {"text": "👨‍💻 Generate Code", "callback_data": f"agent:generate_code:{proposal_id}"},
                ],
                [
                    {"text": "🧩 Apply Patch", "callback_data": f"agent:apply_patch:{proposal_id}"},
                    {"text": "🧪 Start Shadow", "callback_data": f"agent:start_shadow:{proposal_id}"},
                ],
                [
                    {"text": "⏸ Postpone", "callback_data": f"agent:postpone:{proposal_id}"},
                    {"text": "🧮 Simulate", "callback_data": f"agent:simulate:{proposal_id}"},
                    {"text": "✅ Run Tests", "callback_data": f"agent:run_tests:{proposal_id}"},
                ],
                [
                    {"text": "🧾 View Diff", "callback_data": f"agent:view_diff:{proposal_id}"},
                    {"text": "↩️ Rollback", "callback_data": f"agent:rollback:{proposal_id}"},
                    {"text": "📈 Impact", "callback_data": f"agent:impact:{proposal_id}"},
                ],
                [
                    {"text": "📚 History", "callback_data": f"agent:history:{proposal_id}"},
                    {"text": "🧠 Edge Memory", "callback_data": f"agent:edge_memory:{proposal_id}"},
                    {"text": "🧑‍⚖️ Agent Review", "callback_data": f"agent:agent_review:{proposal_id}"},
                ]
            ]
        },
    }


def resolve_qic_telegram_config(settings: object) -> dict[str, Any]:
    # Single source of truth for WHO to talk to (bot token + chat id): load_qic_telegram_config(),
    # the same resolver the listener and approval worker use. `settings` only controls WHETHER
    # QIC is allowed to send (an explicit opt-in flag) and cosmetic delivery preferences — it must
    # never diverge from the listener on which chat/bot is actually being used.
    config = load_qic_telegram_config()
    token = str(config.get("bot_token") or "")
    chat_id = str(config.get("chat_id") or "")
    chat_ids = config.get("chat_ids") or _chat_ids(chat_id)
    source = str(config.get("source") or "missing")

    enabled = _as_bool(getattr(settings, "qic_telegram_enabled", False))
    if not enabled:
        enabled = _as_bool(getattr(settings, "agent_telegram_approval_enabled", False))

    return {
        "enabled": enabled,
        "bot_token": token,
        "chat_ids": chat_ids,
        "chat_id": chat_id,
        "send_no_actionable": _as_bool(getattr(settings, "qic_telegram_send_no_actionable", True)),
        "min_priority": str(getattr(settings, "qic_telegram_min_priority", "MEDIUM") or "MEDIUM"),
        "configured": bool(token and chat_id),
        "source": source,
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
    from trading_signals.agents.implementation.approval_pipeline import approval_auto_apply_config

    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    conditions = context.get("conditions") or proposal.get("conditions") or [proposal.get("title")]
    rule = ", ".join(str(item) for item in conditions if item)
    baseline_pf = context.get("baseline_pf")
    baseline_total_r = context.get("baseline_total_r")
    remaining = int(proposal.get("baseline_trades") or 0) - int(proposal.get("trades_lost") or 0)
    recommendation = "Implementar con feature flag reversible." if proposal.get("edge_type") == "STRUCTURAL_EDGE" else "Revisar manualmente antes de cualquier cambio."
    automation_notice = (
        "Al pulsar Approve, el cambio se revisará, probará y aplicará automáticamente. "
        "Si falla la validación, se realizará rollback."
        if approval_auto_apply_config()["enabled"]
        else "No se ejecutará ningún cambio automáticamente."
    )
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
        + automation_notice
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
    chat_id: str = "",
    rejection_reason: str = "",
) -> dict[str, Any]:
    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "agent":
        return {"handled": False, "reason": "invalid_callback"}
    action, proposal_id = parts[1], parts[2]
    if action in {"details", "debate", "alternative", "start_shadow", "simulate", "run_tests", "view_diff", "rollback", "impact"}:
        return _handle_safe_action_request(
            action,
            proposal_id,
            proposal_store_path=proposal_store_path,
            qic_output_path=qic_output_path,
            actor=actor,
        )
    if action == "postpone":
        updated = update_proposal_status(
            proposal_id,
            "postponed",
            path=proposal_store_path,
            actor=actor,
            approval_metadata={"postponed": True},
        )
        return {"handled": updated is not None, "action": action, "proposal_id": proposal_id, "status": "postponed" if updated else "not_found"}
    if action == "history":
        return _handle_history_callback(proposal_id, proposal_store_path=proposal_store_path, qic_output_path=qic_output_path)
    if action == "edge_memory":
        return _handle_edge_memory_callback(proposal_id, proposal_store_path=proposal_store_path, qic_output_path=qic_output_path)
    if action == "agent_review":
        return _handle_agent_review_callback(qic_output_path=qic_output_path)
    if action == "revalidate":
        return _handle_revalidate_callback(
            proposal_id,
            proposal_store_path=proposal_store_path,
            knowledge_base_path=knowledge_base_path,
            qic_output_path=qic_output_path,
        )
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
    if action == "generate_code":
        return _handle_generate_code_callback(proposal_id, proposal_store_path=proposal_store_path, qic_output_path=qic_output_path)
    if action == "apply_patch":
        return _handle_apply_patch_callback(proposal_id, proposal_store_path=proposal_store_path, qic_output_path=qic_output_path)
    if action not in {"approve", "reject"}:
        return {"handled": False, "reason": "unsupported_action", "action": action}
    if action == "approve":
        return _handle_approve_callback(
            proposal_id,
            proposal_store_path=proposal_store_path,
            knowledge_base_path=knowledge_base_path,
            qic_output_path=qic_output_path,
            actor=actor,
            chat_id=chat_id,
        )
    status = "rejected"
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
            "rejected",
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


def _handle_approve_callback(
    proposal_id: str,
    *,
    proposal_store_path: Path,
    knowledge_base_path: Path,
    qic_output_path: Path,
    actor: str,
    chat_id: str,
) -> dict[str, Any]:
    from trading_signals.agents.implementation.approval_pipeline import (
        approval_auto_apply_config,
        enqueue_approved_proposal_pipeline,
    )
    from trading_signals.agents.proposal_store import load_proposals

    proposal = next((item for item in load_proposals(proposal_store_path) if item.get("id") == proposal_id), None)
    if proposal is None:
        return {
            "handled": False,
            "action": "approve",
            "proposal_id": proposal_id,
            "status": "not_found",
            "reason": "proposal_not_found",
        }
    if proposal.get("status") == "implemented":
        return {
            "handled": True,
            "action": "approve",
            "proposal_id": proposal_id,
            "status": "already_implemented",
            "proposal": proposal,
            "notification_text": "La propuesta ya está implementada; no se ejecutará de nuevo.",
        }

    already_approved = proposal.get("status") in {"approved", "approved_for_implementation_review"}
    updated = proposal
    knowledge_item = None
    if not already_approved:
        updated = update_proposal_status(
            proposal_id,
            "approved_for_implementation_review",
            path=proposal_store_path,
            actor=actor,
            approval_metadata={"human_approved": True},
        )
        if updated is not None:
            knowledge_item = record_proposal_review(updated, "approved", path=knowledge_base_path)
    gate = approval_auto_apply_config()
    if not gate["enabled"]:
        return {
            "handled": updated is not None,
            "action": "approve",
            "proposal_id": proposal_id,
            "status": "approved_for_implementation_review" if updated is not None else "not_found",
            "proposal": updated,
            "knowledge_item": knowledge_item,
            "auto_apply": gate,
            "notification_text": "Propuesta aprobada, pero la aplicación automática está desactivada.",
        }
    queued = enqueue_approved_proposal_pipeline(
        proposal_id=proposal_id,
        proposal_store_path=proposal_store_path,
        knowledge_base_path=knowledge_base_path,
        reports_path=qic_output_path,
        actor=actor,
        chat_id=chat_id,
    )
    status = str(queued.get("status") or "implementation_queue_failed")
    if status == "implementation_queued":
        notification = "⏳ Propuesta aprobada. Iniciando revisión, generación y validación."
    elif status == "already_running":
        notification = "La propuesta ya se está procesando; no se ha iniciado un segundo pipeline."
    elif status == "already_implemented":
        notification = "La propuesta ya está implementada; no se ejecutará de nuevo."
    else:
        notification = "⛔ Propuesta aprobada, pero no se pudo iniciar el worker de implementación."
    return {
        "handled": True,
        "action": "approve",
        "proposal_id": proposal_id,
        "status": status,
        "proposal": updated,
        "knowledge_item": knowledge_item,
        "auto_apply": gate,
        "approval_job": queued,
        "notification_text": notification,
    }


def _handle_history_callback(
    proposal_id: str,
    *,
    proposal_store_path: Path,
    qic_output_path: Path,
) -> dict[str, Any]:
    from trading_signals.agents.decision_ledger import load_decision_ledger, write_decision_ledger_reports

    ledger_path = _qic_data_path(proposal_store_path) / "decision_ledger.jsonl"
    write_decision_ledger_reports(ledger_path=ledger_path, output_path=qic_output_path)
    decisions = load_decision_ledger(ledger_path)
    return {
        "handled": True,
        "action": "history",
        "proposal_id": proposal_id,
        "status": "history_loaded",
        "recent_decisions": decisions[-5:],
    }


def _handle_edge_memory_callback(
    proposal_id: str,
    *,
    proposal_store_path: Path,
    qic_output_path: Path,
) -> dict[str, Any]:
    from trading_signals.agents.proposal_store import load_proposals
    from trading_signals.agents.research_memory import load_research_memory, write_research_memory_reports
    from trading_signals.agents.strategy_knowledge_base import normalize_conditions

    proposals = load_proposals(proposal_store_path)
    proposal = next((item for item in proposals if item.get("id") == proposal_id), None)
    memory_path = _qic_data_path(proposal_store_path) / "research_memory.json"
    memory = load_research_memory(memory_path)
    write_research_memory_reports(memory=memory, output_path=qic_output_path)
    if not proposal:
        return {"handled": True, "action": "edge_memory", "proposal_id": proposal_id, "status": "proposal_not_found"}
    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    target = normalize_conditions(context.get("conditions") or proposal.get("conditions") or [])
    match = next(
        (item for item in (memory.get("experiments") or {}).values() if normalize_conditions(item.get("normalized_conditions") or []) == target),
        None,
    )
    return {
        "handled": True,
        "action": "edge_memory",
        "proposal_id": proposal_id,
        "status": "edge_memory_loaded" if match else "edge_memory_not_found",
        "edge_memory": match,
    }


def _handle_agent_review_callback(*, qic_output_path: Path) -> dict[str, Any]:
    from trading_signals.agents.agent_self_evaluation import evaluate_agents

    report = evaluate_agents(output_path=qic_output_path)
    return {
        "handled": True,
        "action": "agent_review",
        "status": "agent_review_loaded",
        "agents": report.get("agents", {}),
    }


def _handle_revalidate_callback(
    proposal_id: str,
    *,
    proposal_store_path: Path,
    knowledge_base_path: Path,
    qic_output_path: Path,
) -> dict[str, Any]:
    from trading_signals.agents.proposal_store import load_proposals
    from trading_signals.agents.revalidation_engine import run_revalidation_engine
    from trading_signals.agents.strategy_knowledge_base import normalize_conditions

    data_path = _qic_data_path(proposal_store_path).parent
    report = run_revalidation_engine(
        knowledge_base_path=knowledge_base_path,
        research_memory_path=data_path / "qic" / "research_memory.json",
        reports_root=qic_output_path.parent,
        output_path=qic_output_path,
    )
    proposal = next((item for item in load_proposals(proposal_store_path) if item.get("id") == proposal_id), None)
    target = normalize_conditions((proposal.get("context") or {}).get("conditions") if isinstance((proposal or {}).get("context"), dict) else (proposal or {}).get("conditions") or [])
    match = next((item for item in report.get("results", []) if normalize_conditions(item.get("conditions") or []) == target), None)
    return {
        "handled": True,
        "action": "revalidate",
        "proposal_id": proposal_id,
        "status": "revalidated",
        "revalidation": match or report.get("summary", {}),
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


def _handle_generate_code_callback(
    proposal_id: str,
    *,
    proposal_store_path: Path,
    qic_output_path: Path,
) -> dict[str, Any]:
    from trading_signals.agents.implementation.code_engineer import run_code_engineer

    report = run_code_engineer(
        proposal_id=proposal_id,
        proposal_store_path=proposal_store_path,
        reports_path=qic_output_path,
        dry_run=True,
        apply=False,
        run_tests=False,
        allow_apply=False,
    )
    return {
        "handled": True,
        "action": "generate_code",
        "proposal_id": proposal_id,
        "status": report.get("status"),
        "code_engineer": {
            "files_planned": report.get("files_planned", []),
            "blockers": report.get("blockers", []),
            "tests_passed": report.get("tests_passed"),
        },
    }


def _handle_apply_patch_callback(
    proposal_id: str,
    *,
    proposal_store_path: Path,
    qic_output_path: Path,
) -> dict[str, Any]:
    import os
    from trading_signals.agents.implementation.code_engineer import run_code_engineer

    enabled = _as_bool(os.getenv("QIC_CODE_ENGINEER_ENABLED", "false"))
    allow_apply = _as_bool(os.getenv("QIC_CODE_ENGINEER_ALLOW_APPLY", "false"))
    if not enabled or not allow_apply:
        return {
            "handled": True,
            "action": "apply_patch",
            "proposal_id": proposal_id,
            "status": "blocked",
            "reason": "qic_code_engineer_apply_disabled",
        }
    report = run_code_engineer(
        proposal_id=proposal_id,
        proposal_store_path=proposal_store_path,
        reports_path=qic_output_path,
        dry_run=False,
        apply=True,
        run_tests=True,
        allow_apply=True,
    )
    return {
        "handled": True,
        "action": "apply_patch",
        "proposal_id": proposal_id,
        "status": report.get("status"),
        "code_engineer": {
            "files_modified": report.get("files_modified", []),
            "tests_passed": report.get("tests_passed"),
            "blockers": report.get("blockers", []),
        },
    }


def _qic_data_path(proposal_store_path: Path) -> Path:
    # data/agent_proposals/proposals.jsonl -> data/qic
    if proposal_store_path.parent.name == "agent_proposals":
        return proposal_store_path.parent.parent / "qic"
    return Path("data") / "qic"


def process_approval_update(
    update: dict[str, Any],
    *,
    proposal_store_path: Path = DEFAULT_PROPOSALS_PATH,
    knowledge_base_path: Path = DEFAULT_KNOWLEDGE_BASE_PATH,
    qic_output_path: Path = Path("reports") / "qic",
    authorized_chat_ids: list[str] | None = None,
    callback_history_path: Path = DEFAULT_QIC_CALLBACK_HISTORY_PATH,
) -> dict[str, Any]:
    if callback_history_path == DEFAULT_QIC_CALLBACK_HISTORY_PATH and proposal_store_path != DEFAULT_PROPOSALS_PATH:
        callback_history_path = proposal_store_path.parent / "qic_telegram_callbacks.jsonl"
    callback = update.get("callback_query") if isinstance(update.get("callback_query"), dict) else {}
    data = str(callback.get("data") or "")
    actor = str((callback.get("from") or {}).get("id") or "telegram_dev")
    chat_id = str(((callback.get("message") or {}).get("chat") or {}).get("id") or actor)
    if authorized_chat_ids is not None and chat_id not in {str(item) for item in authorized_chat_ids}:
        return {
            "handled": False,
            "reason": "unauthorized_chat",
            "chat_id": chat_id,
            "update_id": update.get("update_id"),
            "callback_query_id": callback.get("id"),
        }
    if not data:
        return {"handled": False, "reason": "missing_callback_data", "update_id": update.get("update_id")}
    callback_id = str(callback.get("id") or "")
    if callback_id and _callback_seen(callback_history_path, callback_id):
        return {
            "handled": True,
            "reason": "duplicate_callback_ignored",
            "idempotent": True,
            "update_id": update.get("update_id"),
            "callback_query_id": callback_id,
        }
    result = handle_approval_callback(
        data,
        proposal_store_path=proposal_store_path,
        knowledge_base_path=knowledge_base_path,
        qic_output_path=qic_output_path,
        actor=actor,
        chat_id=chat_id,
    )
    result["update_id"] = update.get("update_id")
    result["callback_query_id"] = callback_id
    result["actor"] = actor
    result["chat_id"] = chat_id
    result["processed_at"] = utc_now()
    if callback_id:
        append_jsonl(
            callback_history_path,
            {
                "callback_id": callback_id,
                "update_id": update.get("update_id"),
                "actor": actor,
                "chat_id": chat_id,
                "callback_data": data,
                "processed_at": result["processed_at"],
                "result": {"handled": result.get("handled"), "action": result.get("action"), "status": result.get("status"), "reason": result.get("reason")},
            },
        )
    _record_telegram_decision(result, proposal_store_path=proposal_store_path, actor=actor)
    return result


def process_telegram_update(
    update: dict[str, Any],
    *,
    proposal_store_path: Path = DEFAULT_PROPOSALS_PATH,
    knowledge_base_path: Path = DEFAULT_KNOWLEDGE_BASE_PATH,
    qic_output_path: Path = Path("reports") / "qic",
    authorized_chat_ids: list[str] | None = None,
    callback_history_path: Path = DEFAULT_QIC_CALLBACK_HISTORY_PATH,
) -> dict[str, Any]:
    if isinstance(update.get("callback_query"), dict):
        return process_approval_update(
            update,
            proposal_store_path=proposal_store_path,
            knowledge_base_path=knowledge_base_path,
            qic_output_path=qic_output_path,
            authorized_chat_ids=authorized_chat_ids,
            callback_history_path=callback_history_path,
        )
    message = update.get("message") if isinstance(update.get("message"), dict) else {}
    chat_id = str((message.get("chat") or {}).get("id") or "")
    if authorized_chat_ids is not None and chat_id not in {str(item) for item in authorized_chat_ids}:
        return {"handled": False, "reason": "unauthorized_chat", "chat_id": chat_id, "update_id": update.get("update_id")}
    text = str(message.get("text") or "").strip()
    if not text.startswith("/"):
        return {"handled": False, "reason": "unsupported_message", "chat_id": chat_id, "update_id": update.get("update_id")}
    command = text.split()[0].split("@")[0].lower()
    response = build_qic_command_response(
        command,
        proposal_store_path=proposal_store_path,
        qic_output_path=qic_output_path,
    )
    return {
        "handled": True,
        "action": "command",
        "command": command,
        "chat_id": chat_id,
        "update_id": update.get("update_id"),
        "response_text": response,
        "processed_at": utc_now(),
    }


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
    authorized_chat_ids: list[str] | None = None,
    callback_history_path: Path = DEFAULT_QIC_CALLBACK_HISTORY_PATH,
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
        result = process_telegram_update(
            update,
            proposal_store_path=proposal_store_path,
            knowledge_base_path=knowledge_base_path,
            qic_output_path=qic_output_path,
            authorized_chat_ids=authorized_chat_ids,
            callback_history_path=callback_history_path,
        )
        processed.append(result)
        try:
            max_update_id = max(max_update_id, int(update.get("update_id")))
        except (TypeError, ValueError):
            pass
        callback_query_id = result.get("callback_query_id")
        if callback_query_id and not dry_run:
            _answer_callback_query(bot_token, str(callback_query_id), result)
        if result.get("response_text") and result.get("chat_id") and not dry_run:
            _send_payload(
                bot_token,
                {"chat_id": result["chat_id"], "text": result["response_text"], "reply_markup": {"inline_keyboard": []}},
                proposal_id=f"command:{result.get('command')}",
            )
        if result.get("notification_text") and result.get("chat_id") and not dry_run:
            send_qic_status_message(
                bot_token=bot_token,
                chat_id=str(result["chat_id"]),
                text=str(result["notification_text"]),
                proposal_id=str(result.get("proposal_id") or "approval"),
            )
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


def send_qic_status_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    proposal_id: str = "qic_status",
) -> dict[str, Any]:
    if not bot_token or not chat_id:
        return {"status": "skipped", "proposal_id": proposal_id, "reason": "qic_telegram_not_configured"}
    return _send_payload(
        bot_token,
        {"chat_id": chat_id, "text": text[:3900], "reply_markup": {"inline_keyboard": []}},
        proposal_id=proposal_id,
    )


def _get_updates(*, bot_token: str, offset: int, limit: int, timeout: int, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"status": "dry_run", "updates": []}
    query = urllib.parse.urlencode(
        {
            "offset": offset,
            "limit": limit,
            "timeout": timeout,
            "allowed_updates": json.dumps(["callback_query", "message"]),
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
    atomic_write_json(path, {"next_offset": next_offset, "updated_at": datetime.now(tz=UTC).isoformat()})


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _chat_ids(chat_id: str) -> list[str]:
    return [item.strip() for item in str(chat_id).split(",") if item.strip()]


def build_qic_command_response(
    command: str,
    *,
    proposal_store_path: Path = DEFAULT_PROPOSALS_PATH,
    qic_output_path: Path = Path("reports") / "qic",
) -> str:
    proposals = _load_proposals_for_command(proposal_store_path)
    if command in {"/start", "/help"}:
        return (
            "🤖 QIC DEV commands\n"
            "/status /health /qic /research /proposals /pending /history\n"
            "/performance /agents /memory /edges /errors /help"
        )
    if command == "/status":
        run = read_json_safe(qic_output_path / "autonomous_run.json", {})
        state = read_json_safe(qic_output_path / "state_of_council.json", {})
        return _compact("QIC Status", {"run": run.get("status"), "run_id": run.get("run_id"), "score": (read_json_safe(qic_output_path / "system_health.json", {}) or {}).get("autonomous_score"), "pending": state.get("pending_approval")})
    if command == "/health":
        report = read_json_safe(qic_output_path / "system_health.json", {})
        return _compact("QIC Health", {"status": report.get("status"), "score": report.get("autonomous_score"), "errors": report.get("recent_errors")})
    if command == "/qic":
        report = read_json_safe(qic_output_path / "proposal.json", {})
        return _compact("Latest CIO proposal", {"id": report.get("id"), "action": report.get("action"), "title": report.get("title"), "risk": report.get("risk_level")})
    if command == "/research":
        report = read_json_safe(qic_output_path / "revalidation.json", {})
        return _compact("Research", {"revalidation": report.get("summary"), "generated": report.get("status")})
    if command in {"/proposals", "/pending"}:
        selected = [item for item in proposals if command == "/proposals" or item.get("status") in {"pending", "postponed", "approved_for_implementation_review"}]
        lines = [f"📋 {command[1:].title()}: {len(selected)}"]
        lines.extend(f"- {item.get('id')} | {item.get('status')} | {item.get('risk_level')}" for item in selected[-8:])
        return "\n".join(lines)
    if command == "/history":
        report = read_json_safe(qic_output_path / "decision_ledger.json", {})
        decisions = report.get("decisions") if isinstance(report, dict) else []
        lines = [f"📚 QIC History: {len(decisions or [])}"]
        lines.extend(f"- {item.get('proposal_id')} | {item.get('final_decision')} | {item.get('human_action')}" for item in (decisions or [])[-8:])
        return "\n".join(lines)
    if command == "/performance":
        overview = read_json_safe(qic_output_path.parent / "strategy_simulator" / "overview.json", {})
        baseline = overview.get("baseline") if isinstance(overview, dict) else {}
        return _compact("Performance", baseline or {})
    if command == "/agents":
        activity = read_json_safe(qic_output_path.parent.parent / "data" / "qic" / "agent_activity.json", {})
        if not activity:
            activity = read_json_safe(Path("data") / "qic" / "agent_activity.json", {})
        lines = ["🧑‍⚖️ QIC Agents"]
        lines.extend(f"- {name}: {item.get('last_status')} | 24h={item.get('executions_last_24h', 0)}" for name, item in (activity.get("agents") or {}).items())
        return "\n".join(lines)
    if command in {"/memory", "/edges"}:
        filename = "research_memory.json" if command == "/memory" else "strategy_knowledge_base.json"
        report = read_json_safe(qic_output_path / filename, {})
        items = report.get("experiments") or report.get("items") or {}
        return _compact(command[1:].title(), {"items": len(items), "updated_at": report.get("updated_at")})
    if command == "/errors":
        health = read_json_safe(qic_output_path / "system_health.json", {})
        run = read_json_safe(qic_output_path / "autonomous_run.json", {})
        return _compact("Recent errors", {"health_errors": health.get("recent_errors"), "run_errors": run.get("errors", [])[-5:]})
    return "Unknown command. Use /help."


def _handle_safe_action_request(
    action: str,
    proposal_id: str,
    *,
    proposal_store_path: Path,
    qic_output_path: Path,
    actor: str,
) -> dict[str, Any]:
    if action in {"details", "debate", "view_diff", "impact"}:
        filename = {"details": "proposal.json", "debate": "debate.json", "view_diff": "generated_patch.json", "impact": "implementation_review.json"}[action]
        return {"handled": True, "action": action, "proposal_id": proposal_id, "status": "loaded", "details": read_json_safe(qic_output_path / filename, {})}
    if action in {"apply_patch", "rollback", "start_shadow"}:
        return {"handled": True, "action": action, "proposal_id": proposal_id, "status": "blocked", "reason": "explicit_secure_flow_required"}
    request = {
        "request_id": f"telegram_{action}_{proposal_id}_{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S%f')}",
        "action": action,
        "proposal_id": proposal_id,
        "actor": actor,
        "created_at": utc_now(),
        "status": "queued",
    }
    append_jsonl(_qic_data_path(proposal_store_path) / "action_requests.jsonl", request)
    return {"handled": True, "action": action, "proposal_id": proposal_id, "status": "queued", "request_id": request["request_id"]}


def _callback_seen(path: Path, callback_id: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-5000:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(item.get("callback_id") or "") == callback_id:
            return True
    return False


def _record_telegram_decision(result: dict[str, Any], *, proposal_store_path: Path, actor: str) -> None:
    if not result.get("handled") or result.get("idempotent"):
        return
    from trading_signals.agents.decision_ledger import append_decision_ledger_entry

    proposals = _load_proposals_for_command(proposal_store_path)
    proposal = next((item for item in proposals if item.get("id") == result.get("proposal_id")), None)
    append_decision_ledger_entry(
        proposal,
        path=_qic_data_path(proposal_store_path) / "decision_ledger.jsonl",
        final_decision=str(result.get("action") or "telegram_action"),
        human_action=f"telegram:{result.get('action')}:{actor}",
        implementation_status=str(result.get("status") or ""),
    )


def _load_proposals_for_command(path: Path) -> list[dict[str, Any]]:
    from trading_signals.agents.proposal_store import load_proposals

    return load_proposals(path)


def _compact(title: str, values: dict[str, Any]) -> str:
    lines = [f"🤖 {title}"]
    for key, value in values.items():
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)[:3900]
