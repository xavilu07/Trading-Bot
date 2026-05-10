from __future__ import annotations

import csv
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


EXPERIMENTAL_SIGNAL_FIELDS = [
    "timestamp",
    "symbol",
    "direction",
    "entry_price",
    "score",
    "original_block",
    "experimental_reason",
    "real_reason",
    "market_regime",
    "entry_context",
    "rsi",
    "body_ratio",
    "volume_ratio",
    "outcome",
    "max_favorable_move",
    "max_adverse_move",
    "candles_elapsed",
    "exit_reason",
    "evaluated_at",
]


class ExperimentalSignalStore:
    def __init__(self, base_path: Path, *, price_tolerance_pct: float = 0.001) -> None:
        self.signals_file = base_path / "paper_trading" / "experimental_signals.csv"
        self.price_tolerance_pct = price_tolerance_pct
        self.duplicate_skipped_count = 0

    def list_signals(self) -> list[dict[str, str]]:
        if not self.signals_file.exists():
            return []
        with self.signals_file.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def save_signals(self, rows: list[dict[str, object]]) -> None:
        self.signals_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.signals_file.with_suffix(".csv.tmp")
        with temp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=EXPERIMENTAL_SIGNAL_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in EXPERIMENTAL_SIGNAL_FIELDS})
        temp.replace(self.signals_file)

    def upsert_signal(self, row: dict[str, object]) -> bool:
        rows: list[dict[str, object]] = list(self.list_signals())
        if any(self._is_duplicate(existing, row) for existing in rows):
            self.duplicate_skipped_count += 1
            return False
        rows.append(
            {
                **row,
                "outcome": "pending",
                "max_favorable_move": "0",
                "max_adverse_move": "0",
                "candles_elapsed": "0",
                "exit_reason": "",
                "evaluated_at": "",
            }
        )
        self.save_signals(rows)
        return True

    def update_pending_outcomes(
        self,
        market_data,
        *,
        interval: str = "1h",
        win_threshold: float = 0.015,
        loss_threshold: float = 0.01,
        limit: int = 300,
        evaluated_at: str | None = None,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = list(self.list_signals())
        updated: list[dict[str, object]] = []
        evaluated_at = evaluated_at or datetime.now(tz=UTC).isoformat()
        for row in rows:
            if row.get("outcome") != "pending":
                continue
            candles = market_data.fetch_ohlcv(str(row.get("symbol")), interval, limit=limit)
            later_candles = candles_after_timestamp(candles, str(row.get("timestamp", "")))
            result = evaluate_experimental_outcome(
                row,
                later_candles,
                win_threshold=win_threshold,
                loss_threshold=loss_threshold,
            )
            row.update(result)
            row["evaluated_at"] = evaluated_at
            updated.append(dict(row))
        if updated:
            self.save_signals(rows)
        return updated

    def _is_duplicate(self, existing: dict[str, object], candidate: dict[str, object]) -> bool:
        if str(existing.get("outcome", "pending")) != "pending":
            return False
        if str(existing.get("symbol")) != str(candidate.get("symbol")):
            return False
        if str(existing.get("direction")) != str(candidate.get("direction")):
            return False
        if str(existing.get("original_block")) != str(candidate.get("original_block")):
            return False
        return prices_are_similar(
            float(existing.get("entry_price") or 0.0),
            float(candidate.get("entry_price") or 0.0),
            tolerance_pct=self.price_tolerance_pct,
        )

    def build_summary(self) -> dict[str, object]:
        rows = self.list_signals()
        direction_counter = Counter(row.get("direction", "unknown") for row in rows)
        block_counter = Counter(row.get("original_block", "unknown") for row in rows)
        score_counter = Counter(score_bucket(float(row.get("score") or 0.0)) for row in rows)
        closed = [row for row in rows if row.get("outcome") in {"win", "loss"}]
        return {
            "experimental_detected": len(rows),
            "by_direction": dict(direction_counter),
            "by_original_block": dict(block_counter),
            "by_score": dict(score_counter),
            "wins": len([row for row in rows if row.get("outcome") == "win"]),
            "losses": len([row for row in rows if row.get("outcome") == "loss"]),
            "pending": len([row for row in rows if row.get("outcome") == "pending"]),
            "winrate": winrate(closed),
            "winrate_candles_5": mature_winrate(rows, min_candles=5),
            "winrate_candles_10": mature_winrate(rows, min_candles=10),
        }


def build_experimental_signal_row(*, timestamp: str, symbol: str, snapshot, module_diagnostics: dict[str, dict[str, object]]) -> dict[str, object] | None:
    experimental = module_diagnostics.get("experimental_decision_engine", {})
    details = experimental.get("details", {}) if isinstance(experimental.get("details"), dict) else {}
    if details.get("would_send_signal") is not True:
        return None
    momentum = module_diagnostics.get("momentum", {})
    momentum_details = momentum.get("details", {}) if isinstance(momentum.get("details"), dict) else {}
    market_regime = module_diagnostics.get("market_regime", {})
    market_details = market_regime.get("details", {}) if isinstance(market_regime.get("details"), dict) else {}
    strategy_gate = module_diagnostics.get("strategy_gate", {})
    gate_details = strategy_gate.get("details", {}) if isinstance(strategy_gate.get("details"), dict) else {}
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "direction": details.get("direction"),
        "entry_price": snapshot.close,
        "score": details.get("score"),
        "original_block": details.get("original_blocking_filter"),
        "experimental_reason": details.get("experimental_reason"),
        "real_reason": gate_details.get("reason_final"),
        "market_regime": market_details.get("market_regime"),
        "entry_context": market_details.get("entry_context"),
        "rsi": momentum_details.get("rsi"),
        "body_ratio": momentum_details.get("body_ratio"),
        "volume_ratio": momentum_details.get("volume_ratio"),
    }


def format_experimental_summary(summary: dict[str, object]) -> str:
    return (
        "Resumen experimental signals\n"
        f"Detectadas: {summary.get('experimental_detected', 0)}\n"
        f"Wins: {summary.get('wins', 0)} | Losses: {summary.get('losses', 0)} | Pending: {summary.get('pending', 0)}\n"
        f"Winrate provisional: {summary.get('winrate', 0)}%\n"
        f"Winrate candles>=5: {summary.get('winrate_candles_5', {}).get('winrate', 0)}% "
        f"({summary.get('winrate_candles_5', {}).get('closed', 0)} cerradas / {summary.get('winrate_candles_5', {}).get('eligible', 0)} elegibles)\n"
        f"Winrate candles>=10: {summary.get('winrate_candles_10', {}).get('winrate', 0)}% "
        f"({summary.get('winrate_candles_10', {}).get('closed', 0)} cerradas / {summary.get('winrate_candles_10', {}).get('eligible', 0)} elegibles)\n"
        f"Por dirección: {summary.get('by_direction', {})}\n"
        f"Por original_block: {summary.get('by_original_block', {})}\n"
        f"Por score: {summary.get('by_score', {})}"
    )


def winrate(rows: list[dict[str, str]]) -> float:
    if not rows:
        return 0.0
    wins = len([row for row in rows if row.get("outcome") == "win"])
    return round(wins / len(rows) * 100, 2)


def mature_winrate(rows: list[dict[str, str]], *, min_candles: int) -> dict[str, object]:
    eligible = [row for row in rows if int(float(row.get("candles_elapsed") or 0)) >= min_candles]
    closed = [row for row in eligible if row.get("outcome") in {"win", "loss"}]
    return {
        "min_candles": min_candles,
        "eligible": len(eligible),
        "closed": len(closed),
        "wins": len([row for row in closed if row.get("outcome") == "win"]),
        "losses": len([row for row in closed if row.get("outcome") == "loss"]),
        "winrate": winrate(closed),
    }


def candles_after_timestamp(candles: list[dict[str, float | str]], timestamp: str) -> list[dict[str, float | str]]:
    if not timestamp:
        return candles
    entry_ts = datetime.fromisoformat(timestamp).timestamp()
    output = []
    for candle in candles:
        close_time = str(candle.get("close_time") or candle.get("open_time") or "")
        if not close_time:
            continue
        if datetime.fromisoformat(close_time).timestamp() > entry_ts:
            output.append(candle)
    return output


def evaluate_experimental_outcome(
    row: dict[str, object],
    candles: list[dict[str, float | str]],
    *,
    win_threshold: float = 0.015,
    loss_threshold: float = 0.01,
) -> dict[str, object]:
    direction = str(row.get("direction"))
    entry = float(row.get("entry_price") or 0.0)
    if entry <= 0 or not candles:
        return {
            "outcome": "pending",
            "max_favorable_move": row.get("max_favorable_move", "0"),
            "max_adverse_move": row.get("max_adverse_move", "0"),
            "candles_elapsed": str(len(candles)),
            "exit_reason": "",
        }
    max_favorable = float(row.get("max_favorable_move") or 0.0)
    max_adverse = float(row.get("max_adverse_move") or 0.0)
    outcome = "pending"
    exit_reason = ""
    for candle in candles:
        high = float(candle["high"])
        low = float(candle["low"])
        if direction == "long":
            favorable = (high - entry) / entry
            adverse = (entry - low) / entry
        else:
            favorable = (entry - low) / entry
            adverse = (high - entry) / entry
        max_favorable = max(max_favorable, favorable)
        max_adverse = max(max_adverse, adverse)
        if favorable >= win_threshold:
            outcome = "win"
            exit_reason = "favorable_move_reached"
            break
        if adverse >= loss_threshold:
            outcome = "loss"
            exit_reason = "adverse_move_reached"
            break
    return {
        "outcome": outcome,
        "max_favorable_move": f"{max_favorable:.6f}",
        "max_adverse_move": f"{max_adverse:.6f}",
        "candles_elapsed": str(len(candles)),
        "exit_reason": exit_reason,
    }


def score_bucket(score: float) -> str:
    if score >= 90:
        return "90+"
    if score >= 80:
        return "80-89"
    if score >= 75:
        return "75-79"
    return "<75"


def prices_are_similar(left: float, right: float, *, tolerance_pct: float) -> bool:
    if left <= 0 or right <= 0:
        return left == right
    reference = max(abs(left), abs(right))
    return abs(left - right) / reference <= tolerance_pct
