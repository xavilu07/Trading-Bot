from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping


CANONICAL_TRADES_RELATIVE_PATH = Path("paper_trading") / "trades.csv"
CLOSED_STATUSES = {
    "tp2_hit", "tp1_hit", "tp_hit", "sl_hit", "expired", "breakeven", "be_hit", "breakeven_hit",
    "closed", "win", "loss",
}
OPEN_STATUSES = {"", "open", "pending", "active"}
WIN_STATUSES = {"tp2_hit", "tp1_hit", "tp_hit", "win"}
STATISTICAL_KEY_FIELDS = (
    "symbol",
    "timeframe",
    "candle_close",
    "selected_engine",
    "strategy_version",
    "policy_version",
    "experiment_id",
    "universe",
)


class TradeUniverse(StrEnum):
    """Mutually exclusive persistence universes plus a published accepted view."""

    ACCEPTED = "accepted"
    PUBLISHED = "published"
    REJECTED = "rejected"
    SHADOW = "shadow"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TradingCostConfig:
    """Costs expressed in R per completed trade.

    Defaults are deliberately non-zero for commission/spread/slippage so new
    productive metrics are not optimistically gross. Existing rows retain their
    persisted costs; historical rows with no cost evidence are marked unknown
    and use zero only for backwards-compatible arithmetic.
    """

    commission_r: float = 0.02
    spread_r: float = 0.01
    slippage_r: float = 0.01
    funding_r: float = 0.0

    @classmethod
    def from_env(cls) -> "TradingCostConfig":
        return cls(
            commission_r=_env_float("TRADING_COMMISSION_R", 0.02),
            spread_r=_env_float("TRADING_SPREAD_R", 0.01),
            slippage_r=_env_float("TRADING_SLIPPAGE_R", 0.01),
            funding_r=_env_float("TRADING_FUNDING_R", 0.0),
        )

    @property
    def total_cost_r(self) -> float:
        return self.commission_r + self.spread_r + self.slippage_r + self.funding_r


def canonical_trades_path(data_path: Path) -> Path:
    return data_path / CANONICAL_TRADES_RELATIVE_PATH


def load_canonical_trade_rows(data_path: Path) -> list[dict[str, str]]:
    return _read_csv(canonical_trades_path(data_path))


def load_trade_universe(
    data_path: Path,
    universe: TradeUniverse | str = TradeUniverse.ACCEPTED,
    *,
    closed_only: bool = False,
    deduplicate: bool = True,
) -> list[dict[str, Any]]:
    requested = TradeUniverse(str(universe))
    if requested in {TradeUniverse.ACCEPTED, TradeUniverse.PUBLISHED}:
        source = canonical_trades_path(data_path)
        rows = load_canonical_trade_rows(data_path)
        normalized = [
            normalize_trade_row(
                {**row, "_source_row_number": index},
                source=str(source),
                source_universe=TradeUniverse.ACCEPTED,
            )
            for index, row in enumerate(rows, start=1)
        ]
    elif requested is TradeUniverse.SHADOW:
        sources = (
            data_path / "shadow_relaxation" / "trades.csv",
            data_path / "paper_trading" / "shadow_signals.csv",
            data_path / "paper_trading" / "experimental_signals.csv",
        )
        normalized = [
            normalize_trade_row(row, source=str(source), source_universe=TradeUniverse.SHADOW)
            for source in sources
            for index, row in enumerate(_read_csv(source), start=1)
            for row in ({**row, "_source_row_number": index},)
        ]
        normalized.extend(_explicit_rows_from_canonical(data_path, TradeUniverse.SHADOW))
    elif requested is TradeUniverse.REJECTED:
        normalized = [
            *_explicit_rows_from_canonical(data_path, TradeUniverse.REJECTED),
            *_load_rejected_events(data_path),
        ]
    else:
        normalized = []
    rows = [row for row in normalized if row is not None]
    if requested is TradeUniverse.ACCEPTED:
        rows = [row for row in rows if row["universe"] == TradeUniverse.ACCEPTED.value]
    if requested is TradeUniverse.PUBLISHED:
        rows = [
            row for row in rows
            if row["universe"] == TradeUniverse.ACCEPTED.value
            and row["public_published"] is True
            and row.get("published_at")
        ]
    if closed_only:
        rows = [row for row in rows if row["is_closed"]]
    return deduplicate_statistical_rows(rows) if deduplicate else rows


def load_canonical_closed_trades(data_path: Path) -> list[dict[str, Any]]:
    """Productive KPI default: accepted, closed, deduplicated observations."""

    return load_trade_universe(data_path, TradeUniverse.ACCEPTED, closed_only=True)


def load_counterfactual_trades(data_path: Path, *, closed_only: bool = False) -> list[dict[str, Any]]:
    return load_trade_universe(data_path, TradeUniverse.REJECTED, closed_only=closed_only)


def load_shadow_trades(data_path: Path, *, closed_only: bool = False) -> list[dict[str, Any]]:
    return load_trade_universe(data_path, TradeUniverse.SHADOW, closed_only=closed_only)


def canonical_trade_metrics(data_path: Path) -> dict[str, Any]:
    return compute_trade_metrics(load_canonical_closed_trades(data_path), universe=TradeUniverse.ACCEPTED)


def compute_trade_metrics(
    trades: Iterable[Mapping[str, Any]],
    *,
    universe: TradeUniverse | str = TradeUniverse.ACCEPTED,
) -> dict[str, Any]:
    requested = TradeUniverse(str(universe))
    normalized = [
        row if "is_closed" in row else normalize_trade_row(row, source="in-memory", source_universe=requested)
        for row in trades
    ]
    universe_rows = [dict(row) for row in normalized if row is not None and row.get("universe") == requested.value]
    rows = [row for row in universe_rows if row.get("is_closed")]
    expired = [row for row in rows if row.get("status") == "expired"]
    outcomes = [row for row in rows if row.get("status") != "expired"]
    gross = [float(row["gross_result_r"]) for row in outcomes if row.get("gross_result_r") is not None]
    net = [float(row["net_result_r"]) for row in outcomes if row.get("net_result_r") is not None]
    max_drawdown, current_drawdown = drawdowns(net)
    gross_pf = _profit_factor(gross)
    net_pf = _profit_factor(net)
    return {
        "universe": requested.value,
        "closed_trades": len(rows),
        "outcome_trades": len(outcomes),
        "expired_trades": len(expired),
        "open_trades_excluded": len(universe_rows) - len(rows),
        "wins": sum(value > 0 for value in net),
        "losses": sum(value < 0 for value in net),
        "gross_total_r": round(sum(gross), 4),
        "net_total_r": round(sum(net), 4),
        "total_cost_r": round(sum(float(row.get("total_cost") or 0.0) for row in outcomes), 4),
        "gross_expectancy_r": round(sum(gross) / len(gross), 4) if gross else 0.0,
        "net_expectancy_r": round(sum(net) / len(net), 4) if net else 0.0,
        "gross_profit_factor": gross_pf,
        "net_profit_factor": net_pf,
        # Backwards-compatible aliases are explicitly net.
        "total_r": round(sum(net), 4),
        "avg_r": round(sum(net) / len(net), 4) if net else 0.0,
        "profit_factor": net_pf,
        "winrate": round(sum(value > 0 for value in net) / len(net) * 100, 2) if net else 0.0,
        "max_drawdown": round(max_drawdown, 4),
        "current_drawdown": round(current_drawdown, 4),
    }


def normalize_trade_row(
    row: Mapping[str, Any],
    *,
    source: str,
    source_universe: TradeUniverse | str | None = None,
    cost_config: TradingCostConfig | None = None,
) -> dict[str, Any] | None:
    raw = dict(row)
    universe = classify_universe(raw, source_universe=source_universe)
    status = str(raw.get("status") or raw.get("outcome") or "").strip().lower()
    gross = _first_float(raw, ("gross_result_r", "result_r", "r_result", "realized_r"))
    is_closed = status in CLOSED_STATUSES or bool(str(raw.get("closed_at") or "").strip())
    if not status and gross is not None:
        is_closed = True
    if status in OPEN_STATUSES:
        is_closed = False
    historical_cost_unknown = not any(
        str(raw.get(field) or "").strip()
        for field in ("commission", "spread", "slippage", "funding", "total_cost", "net_result_r")
    )
    costs = cost_config or TradingCostConfig.from_env()
    commission = _cost(raw, "commission", costs.commission_r, historical_cost_unknown)
    spread = _cost(raw, "spread", costs.spread_r, historical_cost_unknown)
    slippage = _cost(raw, "slippage", costs.slippage_r, historical_cost_unknown)
    funding = _cost(raw, "funding", costs.funding_r, historical_cost_unknown)
    total_cost = _float(raw.get("total_cost"))
    if total_cost is None:
        total_cost = commission + spread + slippage + funding
    net = _float(raw.get("net_result_r"))
    if net is None and gross is not None:
        net = gross - total_cost
    public_published = _strict_bool(raw.get("public_published"))
    published_at = _first_nonempty(raw, ("published_at", "public_published_at"))
    # Historical truth is conservative: a truthy intention without timestamp is not delivery.
    if not published_at:
        public_published = False
    timestamp = _first_nonempty(
        raw,
        ("closed_at", "updated_at", "evaluated_at", "exit_time", "opened_at", "created_at", "timestamp"),
    )
    normalized = {
        **raw,
        "source": source,
        "source_csv": source,
        "universe": universe.value,
        "accepted": universe is TradeUniverse.ACCEPTED,
        "public_published": public_published,
        "created_at": _first_nonempty(raw, ("created_at", "opened_at", "timestamp")) or "unknown",
        "accepted_at": _first_nonempty(raw, ("accepted_at", "opened_at")) if universe is TradeUniverse.ACCEPTED else "",
        "published_at": published_at,
        "timestamp": timestamp,
        "symbol": str(raw.get("symbol") or "UNKNOWN").strip().upper(),
        "timeframe": _first_nonempty(raw, ("timeframe", "entry_timeframe")) or "unknown",
        "candle_close": _first_nonempty(raw, ("candle_close", "candle_timestamp", "snapshot_timestamp", "opened_at")) or "unknown",
        "selected_engine": str(raw.get("selected_engine") or raw.get("source_engine") or "unknown"),
        "strategy_version": str(raw.get("strategy_version") or "unknown"),
        "policy_version": str(raw.get("policy_version") or "unknown"),
        "experiment_id": str(raw.get("experiment_id") or "none" if universe is TradeUniverse.ACCEPTED else "unknown"),
        "git_commit_sha": str(raw.get("git_commit_sha") or "unknown"),
        "config_hash": str(raw.get("config_hash") or "unknown"),
        "runtime_flags": _json_object(raw.get("runtime_flags")),
        "deployment_id": str(raw.get("deployment_id") or "unknown"),
        "direction": str(raw.get("direction") or "unknown").strip().lower(),
        "setup_type": str(raw.get("setup_type") or "UNKNOWN").strip().upper(),
        "market_regime": _upper_or_unknown(raw.get("market_regime")),
        "session": _upper_or_unknown(raw.get("session")),
        "entry_context": _upper_or_unknown(raw.get("entry_context")),
        "trade_location": str(raw.get("trade_location") or "UNKNOWN").strip() or "UNKNOWN",
        "status": status or "unknown",
        "is_closed": is_closed,
        "gross_result_r": gross,
        # Existing consumers read result_r; canonical normalization makes that alias net.
        "result_r": net,
        "commission": commission,
        "spread": spread,
        "slippage": slippage,
        "funding": funding,
        "total_cost": total_cost,
        "net_result_r": net,
        "costs_known": not historical_cost_unknown,
        "score": _first_float(raw, ("score", "setup_score", "setup_score_final")),
        "volume_ratio": _first_float(raw, ("volume_ratio", "volume_ratio_vs_average_20")),
        "body_ratio": _float(raw.get("body_ratio")),
        "risk_reward": _first_float(raw, ("risk_reward", "risk_reward_tp2", "rr")),
        "trend_entry": str(raw.get("trend_entry") or raw.get("trend_1h") or "").lower(),
        "trend_higher": str(raw.get("trend_higher") or raw.get("trend_4h") or raw.get("trend_higher_timeframe") or "").lower(),
        "opened_hour_utc": str(raw.get("opened_hour_utc") or _hour(timestamp)),
        # Preserve legacy serialization because existing analytical readers
        # parse these columns themselves. Parsed counterparts are additive.
        "warnings": raw.get("warnings") or raw.get("avoidance_warnings") or "",
        "avoidance_warnings": raw.get("avoidance_warnings") or raw.get("warnings") or "",
        "penalties": raw.get("penalties") or "",
        "rejection_reasons": raw.get("rejection_reasons") or raw.get("conditions_failed") or raw.get("entry_or_rejection_reason") or "",
        "warning_tokens": sorted(tokens(raw.get("warnings") or raw.get("avoidance_warnings"))),
        "avoidance_warning_tokens": sorted(tokens(raw.get("avoidance_warnings") or raw.get("warnings"))),
        "penalty_tokens": sorted(tokens(raw.get("penalties"))),
        "rejection_reason_tokens": sorted(
            tokens(raw.get("rejection_reasons") or raw.get("conditions_failed") or raw.get("entry_or_rejection_reason"))
        ),
        "allowed": universe is TradeUniverse.ACCEPTED,
        "blocked": universe is TradeUniverse.REJECTED,
    }
    normalized["statistical_key"] = statistical_key(normalized)
    return normalized


def classify_universe(
    row: Mapping[str, Any],
    *,
    source_universe: TradeUniverse | str | None = None,
) -> TradeUniverse:
    explicit = str(row.get("universe") or "").strip().lower()
    if explicit in {TradeUniverse.ACCEPTED.value, TradeUniverse.REJECTED.value, TradeUniverse.SHADOW.value}:
        return TradeUniverse(explicit)
    if source_universe is not None:
        source = TradeUniverse(str(source_universe))
        return TradeUniverse.ACCEPTED if source is TradeUniverse.PUBLISHED else source
    if _strict_bool(row.get("shadow_only")) or str(row.get("mode") or "").lower() in {"shadow", "experiment"}:
        return TradeUniverse.SHADOW
    if _strict_bool(row.get("accepted")):
        return TradeUniverse.ACCEPTED
    if str(row.get("status") or "").lower() in {"rejected", "no_trade", "blocked"}:
        return TradeUniverse.REJECTED
    return TradeUniverse.UNKNOWN


def statistical_key(row: Mapping[str, Any]) -> str:
    values = [str(row.get(field) or "unknown").strip() for field in STATISTICAL_KEY_FIELDS]
    if any(value.lower() == "unknown" for value in values):
        identity = "|".join(
            str(value)
            for value in (
                row.get("source"),
                row.get("_source_row_number"),
                row.get("trade_id"),
                row.get("signal_id"),
                row.get("dedupe_key"),
                row.get("created_at"),
            )
            if value not in {None, ""}
        )
        return "legacy:" + hashlib.sha256((identity + json.dumps(dict(row), sort_keys=True, default=str)).encode()).hexdigest()
    return "|".join(values)


def deduplicate_statistical_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep the latest technical reevaluation for one statistical observation."""

    by_key: dict[str, dict[str, Any]] = {}
    for item in rows:
        row = dict(item)
        key = str(row.get("statistical_key") or statistical_key(row))
        previous = by_key.get(key)
        if previous is None or _sort_timestamp(row) >= _sort_timestamp(previous):
            by_key[key] = row
    return sorted(by_key.values(), key=_sort_timestamp)


def tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (set, list, tuple)):
        return {str(item).strip() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return {str(item).strip() for item in decoded if str(item).strip()}
    return {item.strip() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip()}


def normalize_for_research(row: dict[str, Any]) -> dict[str, Any] | None:
    return normalize_trade_row(
        row,
        source=str(row.get("source_csv") or row.get("source") or "canonical"),
        source_universe=classify_universe(row),
    )


def is_win(trade: Mapping[str, Any], *, net: bool = True) -> bool:
    field = "net_result_r" if net else "gross_result_r"
    result = _float(trade.get(field))
    return result is not None and result > 0


def drawdowns(values: list[float]) -> tuple[float, float]:
    cumulative = peak = max_drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return max_drawdown, cumulative - peak


def _load_rejected_events(data_path: Path) -> list[dict[str, Any]]:
    path = data_path / "bot_activity" / "signals_log.jsonl"
    if not path.exists():
        return []
    output = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if classify_universe(row) is not TradeUniverse.REJECTED:
                continue
            normalized = normalize_trade_row(row, source=str(path), source_universe=TradeUniverse.REJECTED)
            if normalized:
                output.append(normalized)
    return output


def _explicit_rows_from_canonical(data_path: Path, universe: TradeUniverse) -> list[dict[str, Any]]:
    path = canonical_trades_path(data_path)
    output: list[dict[str, Any]] = []
    for index, row in enumerate(_read_csv(path), start=1):
        if str(row.get("universe") or "").strip().lower() != universe.value:
            continue
        normalized = normalize_trade_row(
            {**row, "_source_row_number": index},
            source=str(path),
            source_universe=universe,
        )
        if normalized:
            output.append(normalized)
    return output


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except (OSError, csv.Error):
        return []


def _cost(row: Mapping[str, Any], field: str, default: float, historical_unknown: bool) -> float:
    value = _float(row.get(field))
    if value is not None:
        return value
    return 0.0 if historical_unknown else default


def _profit_factor(values: list[float]) -> float:
    profit = sum(max(0.0, value) for value in values)
    loss = abs(sum(min(0.0, value) for value in values))
    return round(profit / loss, 4) if loss else (round(profit, 4) if profit else 0.0)


def _sort_timestamp(row: Mapping[str, Any]) -> str:
    return _first_nonempty(row, ("updated_at", "closed_at", "accepted_at", "created_at", "timestamp"))


def _strict_bool(value: object) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _first_nonempty(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _first_float(row: Mapping[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _float(row.get(key))
        if value is not None:
            return value
    return None


def _upper_or_unknown(value: object) -> str:
    text = str(value or "").strip()
    return text.upper() if text else "UNKNOWN"


def _hour(value: object) -> str:
    if not value:
        return "UNKNOWN"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "UNKNOWN"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return str(parsed.astimezone(UTC).hour)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
