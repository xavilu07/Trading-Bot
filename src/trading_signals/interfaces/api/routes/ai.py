from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trading_signals.application.use_cases.dashboard_reader import build_dashboard_summary
from trading_signals.application.use_cases.paper_stats import build_paper_performance_summary
from trading_signals.data.canonical_trade_source import TradeUniverse, load_trade_universe

router = APIRouter(prefix="/ai", tags=["ai"])

TRADING_TERMS = {
    "bot",
    "trade",
    "trades",
    "trading",
    "paper",
    "live",
    "short",
    "shorts",
    "long",
    "longs",
    "signal",
    "signals",
    "senal",
    "senales",
    "señal",
    "señales",
    "rechazo",
    "rechazos",
    "rejection",
    "performance",
    "rendimiento",
    "winrate",
    "profit",
    "pnl",
    "rr",
    "r:r",
    "setup",
    "direction",
    "direccion",
    "dirección",
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str
    used_context: bool
    model: str


@router.post("/chat")
def chat(payload: ChatRequest) -> ChatResponse:
    question = payload.message.strip()
    use_context = _is_trading_question(question)
    prompt = _build_prompt(question, context=_build_trading_context() if use_context else None)
    answer = _generate_gemini_response(prompt)
    return ChatResponse(answer=answer, used_context=use_context, model=_gemini_model())


def _is_trading_question(question: str) -> bool:
    normalized = (
        question.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    tokens = {token.strip(".,;:!?¿¡()[]{}\"'") for token in normalized.split()}
    return bool(tokens & TRADING_TERMS)


def _build_prompt(question: str, *, context: dict[str, Any] | None) -> str:
    if context is None:
        return (
            "Responde como una IA conversacional normal, natural y breve si encaja. "
            "No menciones métricas, estado del bot, señales ni trading salvo que el usuario lo pida.\n\n"
            f"Usuario: {question}"
        )

    return (
        "Eres el asistente del bot de trading. Responde en español natural, sin formato rígido. "
        "Usa el contexto real incluido para preguntas sobre el bot, trades, señales, rendimiento, "
        "direcciones long/short o rechazos. No inventes datos. Si una conclusión no está soportada "
        "por el contexto, dilo. Corrige al usuario solo si contradice datos reales.\n\n"
        "Contexto real del bot en JSON:\n"
        f"{json.dumps(context, ensure_ascii=False, default=str)}\n\n"
        f"Usuario: {question}"
    )


def _build_trading_context() -> dict[str, Any]:
    data_path = Path("data")
    paper_trades_path = data_path / "paper_trading" / "trades.csv"
    live_trades_path = data_path / "live_trading" / "trades.csv"
    signals_log_path = data_path / "bot_activity" / "signals_log.jsonl"

    paper_summary = build_paper_performance_summary(data_path)
    dashboard_summary = build_dashboard_summary(data_path=data_path, latest_limit=10)
    paper_trades = load_trade_universe(data_path, universe=TradeUniverse.ACCEPTED)
    live_trades = _read_csv(live_trades_path)
    signals_log = _read_jsonl_tail(signals_log_path, limit=30)

    return {
        "summary": {
            "paper_stats": paper_summary,
            "dashboard": {
                "last_cycle": dashboard_summary.get("last_cycle"),
                "latest_signals": dashboard_summary.get("latest_signals"),
                "latest_rejections": dashboard_summary.get("latest_rejections"),
                "top_rejection_reasons": dashboard_summary.get("top_rejection_reasons"),
            },
        },
        "trades_csv": {
            "paper": {
                "path": str(paper_trades_path),
                "universe": TradeUniverse.ACCEPTED.value,
                "rows": len(paper_trades),
                "latest_rows": _latest_trade_rows(paper_trades, limit=20),
            },
            "live": {
                "path": str(live_trades_path),
                "rows": len(live_trades),
                "latest_rows": _latest_trade_rows(live_trades, limit=20),
            },
        },
        "direction_performance": {
            "paper": paper_summary.get("by_direction", {}),
            "live": _direction_performance(live_trades),
            "combined": _direction_performance([*paper_trades, *live_trades]),
        },
        "signals_log": {
            "path": str(signals_log_path),
            "latest_entries": signals_log,
            "latest_rejection_reasons": _signals_rejection_reasons(signals_log),
        },
        "rejection_reasons": {
            "dashboard_top": dashboard_summary.get("top_rejection_reasons", []),
            "paper_top": paper_summary.get("top_rejection_reasons", []),
            "conditions_failed_top": paper_summary.get("top_failed_conditions", []),
            "avoidance_warnings_top": paper_summary.get("top_avoidance_warnings", []),
        },
    }


def _generate_gemini_response(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Missing GEMINI_API_KEY or GOOGLE_API_KEY")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Missing google-genai dependency") from exc

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=_gemini_model(),
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=900,
        ),
    )
    text = getattr(response, "text", None)
    if not text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response")
    return str(text).strip()


def _gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in deque(handle, maxlen=limit):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def _latest_trade_rows(rows: list[dict[str, str]], *, limit: int) -> list[dict[str, Any]]:
    keys = (
        "opened_at",
        "created_at",
        "updated_at",
        "closed_at",
        "symbol",
        "direction",
        "setup_type",
        "score",
        "status",
        "result_r",
        "entry_or_rejection_reason",
        "conditions_failed",
        "avoidance_warnings",
        "market_regime",
        "session",
        "entry_context",
    )
    sorted_rows = sorted(rows, key=lambda row: _row_time(row), reverse=True)
    return [{key: row.get(key, "") for key in keys if key in row} for row in sorted_rows[:limit]]


def _direction_performance(rows: list[dict[str, str]]) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if not _is_closed(row):
            continue
        groups[str(row.get("direction") or "UNKNOWN").lower()].append(row)

    output: dict[str, dict[str, float | int]] = {}
    for direction, items in groups.items():
        total_r = sum(_float(item.get("result_r")) for item in items)
        wins = len([item for item in items if _float(item.get("result_r")) > 0])
        losses = len([item for item in items if _float(item.get("result_r")) < 0])
        output[direction] = {
            "trades": len(items),
            "wins": wins,
            "losses": losses,
            "winrate": round(wins / len(items) * 100, 2) if items else 0.0,
            "total_r": round(total_r, 4),
            "avg_r": round(total_r / len(items), 4) if items else 0.0,
        }
    return output


def _signals_rejection_reasons(rows: list[dict[str, Any]]) -> list[dict[str, int | str]]:
    counter: Counter[str] = Counter()
    for row in rows:
        reasons = row.get("rejection_reasons")
        if isinstance(reasons, list):
            counter.update(str(reason) for reason in reasons if reason)
        elif reasons:
            counter.update(str(reasons).split("|"))
    return [{"label": label, "count": count} for label, count in counter.most_common(10) if label.strip()]


def _is_closed(row: dict[str, str]) -> bool:
    status = str(row.get("status") or "").lower()
    return status in {"tp2_hit", "tp_hit", "sl_hit", "expired"} or bool(str(row.get("closed_at") or "").strip())


def _row_time(row: dict[str, str]) -> str:
    return str(row.get("updated_at") or row.get("closed_at") or row.get("opened_at") or row.get("created_at") or "")


def _float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
