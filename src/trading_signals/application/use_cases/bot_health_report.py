from __future__ import annotations

import json
from collections import Counter, deque
from pathlib import Path
from typing import Any


MAX_TELEGRAM_CHARS = 1200
DEFAULT_SIGNAL_WINDOW = 250


def build_bot_health_report(
    *,
    data_path: Path,
    reports_path: Path,
    min_score: float = 70.0,
    max_signals: int = DEFAULT_SIGNAL_WINDOW,
) -> dict[str, object]:
    report_path = reports_path / "bot_health_report.json"
    external = _read_report_json(report_path)
    if external:
        return _normalize_external_report(external, min_score=min_score)
    rows = _read_jsonl_tail(data_path / "bot_activity" / "signals_log.jsonl", max_lines=max_signals)
    return _build_from_signal_rows(rows, min_score=min_score)


def format_bot_health_report_for_telegram(report: dict[str, object], *, max_chars: int = MAX_TELEGRAM_CHARS) -> str:
    top_reasons = report.get("top_rejection_reasons", [])
    if isinstance(top_reasons, list) and top_reasons:
        reason_lines = []
        for idx, item in enumerate(top_reasons[:3], start=1):
            if isinstance(item, dict):
                reason_lines.append(f"{idx}. {item.get('reason', 'unknown')}: {item.get('count', 0)}")
        reasons_text = "\n".join(reason_lines) if reason_lines else "- sin datos"
    else:
        reasons_text = "- sin rechazos recientes"

    message = (
        "🩺 Bot Health Report\n"
        f"- Señales emitidas: {report.get('signals_emitted', 0)}\n"
        f"- Señales rechazadas: {report.get('signals_rejected', 0)}\n"
        f"- High score rejects >= {report.get('min_score', 70)}: {report.get('high_score_rejects', 0)}\n"
        f"- Shadow score bloqueado >= {report.get('min_score', 70)}: {report.get('shadow_score_blocked', 0)}\n\n"
        "Top rechazos:\n"
        f"{reasons_text}\n\n"
        f"Diagnóstico: {report.get('diagnosis', 'datos insuficientes')}"
    )
    return _truncate(message, max_chars)


def build_bot_health_telegram_section(
    *,
    data_path: Path,
    reports_path: Path,
    min_score: float = 70.0,
) -> str:
    return format_bot_health_report_for_telegram(
        build_bot_health_report(data_path=data_path, reports_path=reports_path, min_score=min_score)
    )


def _build_from_signal_rows(rows: list[dict[str, Any]], *, min_score: float) -> dict[str, object]:
    emitted = 0
    rejected = 0
    high_score_rejects = 0
    shadow_score_blocked = 0
    reasons: Counter[str] = Counter()

    for row in rows:
        status = str(row.get("status") or "").lower()
        score = _float(row.get("score"))
        if status == "sent":
            emitted += 1
        elif status in {"rejected", "no_trade"}:
            rejected += 1
            if score is not None and score >= min_score:
                high_score_rejects += 1

        for reason in _row_rejection_reasons(row):
            reasons[reason] += 1

        shadow_score = _shadow_score(row)
        if shadow_score is not None and shadow_score >= min_score and status != "sent":
            shadow_score_blocked += 1

    top_reasons = [{"reason": reason, "count": count} for reason, count in reasons.most_common(3)]
    return {
        "source": "signals_log",
        "window_size": len(rows),
        "signals_emitted": emitted,
        "signals_rejected": rejected,
        "top_rejection_reasons": top_reasons,
        "high_score_rejects": high_score_rejects,
        "shadow_score_blocked": shadow_score_blocked,
        "min_score": _clean_number(min_score),
        "diagnosis": _diagnosis(
            emitted=emitted,
            rejected=rejected,
            top_reasons=top_reasons,
            high_score_rejects=high_score_rejects,
            shadow_score_blocked=shadow_score_blocked,
        ),
    }


def _normalize_external_report(raw: dict[str, Any], *, min_score: float) -> dict[str, object]:
    top = raw.get("top_rejection_reasons") or raw.get("rejection_reasons") or []
    if isinstance(top, dict):
        top_reasons = [{"reason": str(reason), "count": count} for reason, count in Counter(top).most_common(3)]
    elif isinstance(top, list):
        top_reasons = [
            item if isinstance(item, dict) else {"reason": str(item), "count": 1}
            for item in top[:3]
        ]
    else:
        top_reasons = []
    emitted = int(_float(raw.get("signals_emitted") or raw.get("signals_sent")) or 0)
    rejected = int(_float(raw.get("signals_rejected") or raw.get("rejected")) or 0)
    high_score_rejects = int(_float(raw.get("high_score_rejects") or raw.get("high_score_rejected")) or 0)
    shadow_score_blocked = int(_float(raw.get("shadow_score_blocked") or raw.get("blocked_shadow_score")) or 0)
    return {
        "source": "bot_health_report_json",
        "signals_emitted": emitted,
        "signals_rejected": rejected,
        "top_rejection_reasons": top_reasons,
        "high_score_rejects": high_score_rejects,
        "shadow_score_blocked": shadow_score_blocked,
        "min_score": _clean_number(raw.get("min_score") or min_score),
        "diagnosis": raw.get("diagnosis") or _diagnosis(
            emitted=emitted,
            rejected=rejected,
            top_reasons=top_reasons,
            high_score_rejects=high_score_rejects,
            shadow_score_blocked=shadow_score_blocked,
        ),
    }


def _row_rejection_reasons(row: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for key in ("rejection_reasons", "conditions_failed"):
        value = row.get(key)
        if isinstance(value, list):
            tokens.extend(str(item) for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            tokens.extend(part.strip() for part in value.replace("|", ",").split(",") if part.strip())
    reason = str(row.get("reasons") or "").strip()
    if reason and reason.lower() != "none":
        tokens.extend(part.strip() for part in reason.replace("|", ",").split(",") if part.strip())
    return _dedupe(tokens)


def _shadow_score(row: dict[str, Any]) -> float | None:
    for key in ("shadow_score", "shadow_decision_score"):
        value = _float(row.get(key))
        if value is not None:
            return value
    raw = row.get("raw_summary")
    if isinstance(raw, dict):
        for key in ("shadow_score", "shadow_decision_score", "parallel_score"):
            value = _float(raw.get(key))
            if value is not None:
                return value
    return None


def _read_report_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _read_jsonl_tail(path: Path, *, max_lines: int) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = deque(handle, maxlen=max_lines)
    except OSError:
        return []
    for line in lines:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


def _diagnosis(
    *,
    emitted: int,
    rejected: int,
    top_reasons: list[dict[str, object]],
    high_score_rejects: int,
    shadow_score_blocked: int,
) -> str:
    if emitted == 0 and rejected == 0:
        return "sin actividad reciente suficiente"
    if emitted == 0 and top_reasons:
        return f"sin señales públicas; bloqueo dominante: {top_reasons[0].get('reason')}"
    if high_score_rejects > 0:
        return "hay candidatos fuertes bloqueados; revisar gates/routing antes de relajar"
    if shadow_score_blocked > 0:
        return "shadow detecta oportunidades; mantenerlas en observación"
    if emitted > 0:
        return "bot activo; validar rendimiento posterior en paper/live"
    return "rechazos presentes, sin patrón dominante claro"


def _truncate(message: str, max_chars: int) -> str:
    if len(message) <= max_chars:
        return message
    suffix = "\n…"
    return message[: max(0, max_chars - len(suffix))].rstrip() + suffix


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_number(value: Any) -> int | float:
    number = _float(value)
    if number is None:
        return 70
    return int(number) if number.is_integer() else number
