from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import pstdev
from typing import Any


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven", "closed", "win", "loss"}
WIN_LABELS = {"TP_HIT", "tp_hit", "tp2_hit", "win"}
LOSS_LABELS = {"SL_HIT", "sl_hit", "loss"}
MATRIX_FIELDS = [
    "validation",
    "status",
    "metric",
    "value",
    "threshold",
    "confidence",
    "details",
]


def load_strategy_validation_records(data_path: Path, reports_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_load_trade_csvs(data_path))
    rows.extend(_load_report_csv(reports_path / "triple_barrier_labels.csv", source="triple_barrier"))
    rows.extend(_load_report_csv(reports_path / "meta_dataset.csv", source="meta_dataset"))
    rows.extend(_load_signal_activity(data_path / "bot_activity" / "signals_log.jsonl"))
    return _dedupe_records([row for row in (_normalize_record(row) for row in rows) if row is not None])


def run_strategy_validation(
    records: list[dict[str, Any]],
    *,
    rolling_window: int = 100,
    delay_candles: int = 1,
) -> dict[str, Any]:
    normalized = [row for row in (_normalize_record(row) for row in records) if row is not None]
    ordered = sorted(normalized, key=lambda row: (row.get("timestamp") or datetime.min.replace(tzinfo=UTC), row.get("record_id", "")))
    closed = [row for row in ordered if row.get("result_r") is not None]
    full_metrics = _metrics(closed)
    rolling_rows = _rolling_windows(closed, rolling_window=max(1, rolling_window))
    chunk_rows = _chunk_windows(closed, rolling_window=max(1, rolling_window))
    delayed = _delayed_execution(closed, delay_candles=max(0, delay_candles))
    checks = [
        _lookahead_bias_check(ordered),
        _recursive_consistency_check(ordered),
        _rolling_stability_check(rolling_rows, full_metrics),
        _candle_close_dependency_check(ordered),
        _timestamp_consistency_check(ordered),
        _delayed_execution_check(delayed, full_metrics),
        _indicator_recalculation_drift_check(ordered),
        _rolling_pf_stability_check(rolling_rows),
        _rolling_wr_stability_check(rolling_rows),
        _overfit_context_check(closed),
    ]
    validation_status = _overall_status(checks)
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "validation_status": validation_status,
        "records_analyzed": len(ordered),
        "closed_records": len(closed),
        "rolling_window": rolling_window,
        "delay_candles": delay_candles,
        "full_history_evaluation": full_metrics,
        "rolling_window_evaluation": _window_summary(rolling_rows),
        "recalculated_chunk_evaluation": _window_summary(chunk_rows),
        "delayed_execution_evaluation": delayed,
        "matrix_rows": checks,
        "setups_that_disappear_after_recalculation": _setup_drift_rows(ordered),
        "signals_dependent_on_future_candles": _future_dependency_rows(ordered),
        "unstable_indicators": _indicator_drift_rows(ordered),
        "unstable_score_regions": _score_region_rows(closed),
        "overfit_contexts": _overfit_context_rows(closed),
        "recommended_actions": _recommended_actions(checks, len(closed)),
        "confidence": _confidence(len(closed)),
    }


def write_strategy_validation_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "strategy_validation_report.json"
    md_path = reports_path / "strategy_validation_summary.md"
    csv_path = reports_path / "strategy_validation_matrix.csv"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md_path.write_text(format_strategy_validation_summary(result), encoding="utf-8")
    _write_csv(csv_path, result.get("matrix_rows", []))
    return {"json_path": json_path, "summary_path": md_path, "matrix_path": csv_path}


def format_strategy_validation_summary(result: dict[str, Any]) -> str:
    full = result.get("full_history_evaluation", {})
    rolling = result.get("rolling_window_evaluation", {})
    delayed = result.get("delayed_execution_evaluation", {})
    lines = [
        "# Strategy Validation Suite",
        "",
        f"- Generated at: {result.get('generated_at')}",
        f"- Validation status: {result.get('validation_status')}",
        f"- Records analyzed: {result.get('records_analyzed', 0)}",
        f"- Closed records: {result.get('closed_records', 0)}",
        f"- Confidence: {result.get('confidence')}",
        "",
        "## Full History",
        "",
        f"- PF: {_pf(full.get('profit_factor'))}",
        f"- WR: {full.get('winrate', 0)}%",
        f"- AvgR: {full.get('avg_r', 0)}",
        f"- Max DD: {full.get('max_drawdown', 0)}",
        "",
        "## Rolling Validation",
        "",
        f"- Windows: {rolling.get('windows', 0)}",
        f"- PF stability: {rolling.get('pf_stability', 0)}",
        f"- WR stability: {rolling.get('wr_stability', 0)}",
        f"- AvgR stability: {rolling.get('avg_r_stability', 0)}",
        "",
        "## Delayed Execution",
        "",
        f"- Delayed records: {delayed.get('delayed_records', 0)}",
        f"- Skipped early resolution: {delayed.get('skipped_early_resolution', 0)}",
        f"- Delayed PF: {_pf(delayed.get('metrics', {}).get('profit_factor'))}",
        f"- Delayed WR: {delayed.get('metrics', {}).get('winrate', 0)}%",
        "",
        "## Validation Matrix",
        "",
        *_format_matrix(result.get("matrix_rows", [])),
        "",
        "## Recommended Actions",
        "",
        *_format_list(result.get("recommended_actions", [])),
    ]
    return "\n".join(lines) + "\n"


def _lookahead_bias_check(records: list[dict[str, Any]]) -> dict[str, Any]:
    suspicious = _future_dependency_rows(records)
    rate = len(suspicious) / len(records) if records else 0.0
    return _matrix_row(
        "lookahead_bias_detection",
        _status(rate, warning=0.01, dangerous=0.05),
        "future_dependency_suspicion_rate",
        round(rate, 4),
        "<=0.01",
        _confidence(len(records)),
        f"{len(suspicious)} suspicious records",
    )


def _recursive_consistency_check(records: list[dict[str, Any]]) -> dict[str, Any]:
    drift = _setup_drift_rows(records)
    rate = len(drift) / max(1, len(records))
    return _matrix_row(
        "recursive_recalculation_consistency",
        _status(rate, warning=0.02, dangerous=0.1),
        "setup_drift_rate",
        round(rate, 4),
        "<=0.02",
        _confidence(len(records)),
        f"{len(drift)} duplicate keys changed setup/score",
    )


def _rolling_stability_check(rows: list[dict[str, Any]], full_metrics: dict[str, Any]) -> dict[str, Any]:
    summary = _window_summary(rows)
    drift = abs(float(summary.get("avg_r_mean", 0.0)) - float(full_metrics.get("avg_r", 0.0)))
    return _matrix_row(
        "rolling_window_validation",
        _status(drift, warning=0.35, dangerous=0.75),
        "avgR_drift_vs_full_history",
        round(drift, 4),
        "<=0.35R",
        _confidence(sum(int(row.get("trades", 0)) for row in rows)),
        f"{summary.get('windows', 0)} rolling windows",
    )


def _candle_close_dependency_check(records: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = []
    for row in records:
        opened = row.get("opened_at")
        candle_close = row.get("signal_candle_close")
        if isinstance(opened, datetime) and isinstance(candle_close, datetime) and opened < candle_close:
            mismatches.append(row)
    rate = len(mismatches) / max(1, len(records))
    return _matrix_row(
        "candle_close_dependency_detection",
        _status(rate, warning=0.01, dangerous=0.05),
        "pre_close_signal_rate",
        round(rate, 4),
        "0 preferred",
        _confidence(len(records)),
        f"{len(mismatches)} records opened before candle close",
    )


def _timestamp_consistency_check(records: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = [
        row for row in records
        if isinstance(row.get("closed_at"), datetime)
        and isinstance(row.get("opened_at"), datetime)
        and row["closed_at"] < row["opened_at"]
    ]
    rate = len(mismatches) / max(1, len(records))
    return _matrix_row(
        "signal_timestamp_consistency",
        _status(rate, warning=0.01, dangerous=0.05),
        "timestamp_mismatch_rate",
        round(rate, 4),
        "0 preferred",
        _confidence(len(records)),
        f"{len(mismatches)} closed_at before opened_at",
    )


def _delayed_execution_check(delayed: dict[str, Any], full_metrics: dict[str, Any]) -> dict[str, Any]:
    delayed_avg = float(delayed.get("metrics", {}).get("avg_r", 0.0))
    full_avg = float(full_metrics.get("avg_r", 0.0))
    drift = abs(delayed_avg - full_avg)
    early_rate = delayed.get("skipped_early_resolution", 0) / max(1, delayed.get("input_records", 0))
    status = max(_status(drift, warning=0.35, dangerous=0.75), _status(early_rate, warning=0.35, dangerous=0.6), key=_status_rank)
    return _matrix_row(
        "delayed_entry_simulation",
        status,
        "delayed_avgR_drift",
        round(drift, 4),
        "<=0.35R",
        _confidence(int(delayed.get("delayed_records", 0))),
        f"early_resolution_rate={round(early_rate, 4)}",
    )


def _indicator_recalculation_drift_check(records: list[dict[str, Any]]) -> dict[str, Any]:
    drift = _indicator_drift_rows(records)
    rate = len(drift) / max(1, len(records))
    return _matrix_row(
        "indicator_recalculation_drift",
        _status(rate, warning=0.03, dangerous=0.1),
        "indicator_or_score_drift_rate",
        round(rate, 4),
        "<=0.03",
        _confidence(len(records)),
        f"{len(drift)} duplicate keys with indicator/score drift",
    )


def _rolling_pf_stability_check(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _window_summary(rows)
    value = float(summary.get("pf_stability", 0.0))
    return _matrix_row("rolling_pf_stability", _status(value, warning=1.0, dangerous=2.0), "pf_stddev", value, "<=1.0", summary.get("confidence", "LOW"), "")


def _rolling_wr_stability_check(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _window_summary(rows)
    value = float(summary.get("wr_stability", 0.0))
    return _matrix_row("rolling_wr_stability", _status(value, warning=25.0, dangerous=40.0), "wr_stddev", value, "<=25", summary.get("confidence", "LOW"), "")


def _overfit_context_check(records: list[dict[str, Any]]) -> dict[str, Any]:
    contexts = _overfit_context_rows(records)
    status = "SAFE" if not contexts else ("WARNING" if len(contexts) <= 3 else "DANGEROUS")
    return _matrix_row(
        "overfit_context_detection",
        status,
        "unstable_contexts",
        len(contexts),
        "<=3",
        _confidence(len(records)),
        "; ".join(f"{row['context']}={row['value']}" for row in contexts[:5]),
    )


def _rolling_windows(records: list[dict[str, Any]], *, rolling_window: int) -> list[dict[str, Any]]:
    if not records:
        return []
    step = max(1, rolling_window // 2)
    rows = []
    for start in range(0, len(records), step):
        window = records[start:start + rolling_window]
        if not window:
            continue
        rows.append({"window": f"{start}:{start + len(window)}", **_metrics(window)})
        if start + rolling_window >= len(records):
            break
    return rows


def _chunk_windows(records: list[dict[str, Any]], *, rolling_window: int) -> list[dict[str, Any]]:
    rows = []
    for start in range(0, len(records), rolling_window):
        chunk = records[start:start + rolling_window]
        if chunk:
            rows.append({"window": f"chunk_{len(rows) + 1}", **_metrics(chunk)})
    return rows


def _delayed_execution(records: list[dict[str, Any]], *, delay_candles: int) -> dict[str, Any]:
    delayed = []
    skipped = 0
    for row in records:
        candles = _int(row.get("candles_held") or row.get("bars_to_label") or row.get("bars_held"))
        if candles is not None and candles <= delay_candles:
            skipped += 1
            continue
        delayed.append(row)
    return {
        "input_records": len(records),
        "delay_candles": delay_candles,
        "delayed_records": len(delayed),
        "skipped_early_resolution": skipped,
        "metrics": _metrics(delayed),
    }


def _window_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pf_values = [_finite_pf(row.get("profit_factor")) for row in rows if _finite_pf(row.get("profit_factor")) is not None]
    wr_values = [float(row.get("winrate") or 0.0) for row in rows]
    avg_r_values = [float(row.get("avg_r") or 0.0) for row in rows]
    dd_values = [float(row.get("max_drawdown") or 0.0) for row in rows]
    return {
        "windows": len(rows),
        "pf_stability": round(pstdev(pf_values), 4) if len(pf_values) > 1 else 0.0,
        "wr_stability": round(pstdev(wr_values), 4) if len(wr_values) > 1 else 0.0,
        "avg_r_stability": round(pstdev(avg_r_values), 4) if len(avg_r_values) > 1 else 0.0,
        "drawdown_stability": round(pstdev(dd_values), 4) if len(dd_values) > 1 else 0.0,
        "avg_r_mean": round(sum(avg_r_values) / len(avg_r_values), 4) if avg_r_values else 0.0,
        "confidence": _confidence(sum(int(row.get("trades", 0)) for row in rows)),
    }


def _metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["result_r"]) for row in records if row.get("result_r") is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(max(0.0, value) for value in values)
    gross_loss = abs(sum(min(0.0, value) for value in values))
    return {
        "trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
        "total_r": round(sum(values), 4),
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (None if gross_profit > 0 else 0.0),
        "max_drawdown": round(_max_drawdown(values), 4),
    }


def _future_dependency_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suspicious = []
    for row in records:
        opened = row.get("opened_at")
        closed = row.get("closed_at")
        if isinstance(opened, datetime) and isinstance(closed, datetime) and opened > closed:
            suspicious.append(row)
        if row.get("source") == "signals_log" and row.get("result_r") is not None and not row.get("closed_at"):
            suspicious.append(row)
    return suspicious


def _setup_drift_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = _group_by_signal_key(records)
    drift = []
    for key, items in grouped.items():
        if len(items) < 2:
            continue
        setups = {str(item.get("setup_type")) for item in items}
        decisions = {str(item.get("direction")) for item in items}
        if len(setups) > 1 or len(decisions) > 1:
            drift.append({"signal_key": key, "setups": sorted(setups), "directions": sorted(decisions), "count": len(items)})
    return drift


def _indicator_drift_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = _group_by_signal_key(records)
    drift = []
    for key, items in grouped.items():
        if len(items) < 2:
            continue
        scores = {_rounded(item.get("score")) for item in items if item.get("score") is not None}
        body = {_rounded(item.get("body_ratio")) for item in items if item.get("body_ratio") is not None}
        volume = {_rounded(item.get("volume_ratio")) for item in items if item.get("volume_ratio") is not None}
        if len(scores) > 1 or len(body) > 1 or len(volume) > 1:
            drift.append({"signal_key": key, "scores": sorted(scores), "body_ratio": sorted(body), "volume_ratio": sorted(volume), "count": len(items)})
    return drift


def _score_region_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[_score_bucket(row.get("score"))].append(row)
    rows = []
    for bucket, items in grouped.items():
        metrics = _metrics(items)
        if int(metrics["trades"]) >= 5 and (float(metrics["avg_r"]) < 0 or float(metrics["winrate"]) < 40):
            rows.append({"score_bucket": bucket, **metrics})
    return sorted(rows, key=lambda row: (float(row["avg_r"]), float(row["winrate"])))


def _overfit_context_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for field in ("direction", "setup_type", "market_regime", "session", "entry_context", "trade_location"):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in records:
            grouped[str(row.get(field) or "UNKNOWN")].append(row)
        for value, items in grouped.items():
            metrics = _metrics(items)
            if int(metrics["trades"]) >= 5 and float(metrics["avg_r"]) < 0 and float(metrics["winrate"]) < 45:
                output.append({"context": field, "value": value, **metrics})
    return sorted(output, key=lambda row: (float(row["avg_r"]), -int(row["trades"])))[:10]


def _group_by_signal_key(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        key = str(row.get("dedupe_key") or row.get("signal_id") or row.get("record_id") or "")
        if not key:
            continue
        grouped[key].append(row)
    return grouped


def _normalize_record(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    timestamp = _first_datetime(row, ("timestamp", "opened_at", "created_at", "closed_at", "updated_at", "evaluated_at"))
    result_r = _float(row.get("result_r") or row.get("r_result") or row.get("realized_r"))
    label = str(row.get("label") or row.get("status") or row.get("outcome") or "").strip()
    if result_r is None:
        if label in WIN_LABELS:
            result_r = 1.0
        elif label in LOSS_LABELS:
            result_r = -1.0
    return {
        **row,
        "record_id": str(row.get("trade_id") or row.get("signal_id") or row.get("dedupe_key") or f"record_{hash(json.dumps(row, default=str, sort_keys=True))}"),
        "timestamp": timestamp,
        "opened_at": _first_datetime(row, ("opened_at", "created_at", "timestamp")),
        "closed_at": _first_datetime(row, ("closed_at", "exit_time", "evaluated_at", "updated_at")),
        "signal_candle_close": _dedupe_candle_time(row.get("dedupe_key")),
        "result_r": result_r,
        "symbol": str(row.get("symbol") or "UNKNOWN").upper(),
        "direction": str(row.get("direction") or "unknown").lower(),
        "setup_type": str(row.get("setup_type") or "UNKNOWN").upper(),
        "market_regime": str(row.get("market_regime") or "UNKNOWN").upper(),
        "session": str(row.get("session") or "UNKNOWN").upper(),
        "entry_context": str(row.get("entry_context") or "UNKNOWN").upper(),
        "trade_location": str(row.get("trade_location") or "UNKNOWN"),
        "score": _float(row.get("score") or row.get("setup_score") or row.get("setup_score_final")),
        "body_ratio": _float(row.get("body_ratio")),
        "volume_ratio": _float(row.get("volume_ratio") or row.get("volume_ratio_vs_average_20")),
        "candles_held": _int(row.get("candles_held") or row.get("bars_to_label") or row.get("bars_held") or row.get("candles_elapsed")),
    }


def _load_trade_csvs(data_path: Path) -> list[dict[str, Any]]:
    paths = []
    paper_path = data_path / "paper_trading"
    if paper_path.exists():
        paths.extend(path for path in paper_path.glob("*.csv") if path.is_file())
    live_path = data_path / "live_trading" / "trades.csv"
    if live_path.exists():
        paths.append(live_path)
    rows = []
    for path in sorted(paths):
        for row in _read_csv(path):
            status = str(row.get("status") or row.get("outcome") or "").strip().lower()
            if status and status not in CLOSED_STATUSES and not row.get("closed_at"):
                continue
            rows.append({**row, "source": f"trade:{path.name}"})
    return rows


def _load_report_csv(path: Path, *, source: str) -> list[dict[str, Any]]:
    return [{**row, "source": source} for row in _read_csv(path)]


def _load_signal_activity(path: Path, *, max_lines: int = 10000) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle.readlines()[-max_lines:]:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append({**item, "source": "signals_log"})
    return rows


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for row in sorted(records, key=lambda item: str(item.get("timestamp") or "")):
        key = (
            row.get("source"),
            row.get("record_id"),
            row.get("symbol"),
            row.get("direction"),
            row.get("timestamp"),
            row.get("result_r"),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except csv.Error:
        return []


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATRIX_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MATRIX_FIELDS})


def _matrix_row(validation: str, status: str, metric: str, value: Any, threshold: str, confidence: str, details: str) -> dict[str, Any]:
    return {
        "validation": validation,
        "status": status,
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "confidence": confidence,
        "details": details,
    }


def _recommended_actions(checks: list[dict[str, Any]], closed_count: int) -> list[str]:
    actions = []
    for row in checks:
        if row["status"] == "DANGEROUS":
            actions.append(f"investigate_immediately:{row['validation']}:{row['details']}")
        elif row["status"] == "WARNING":
            actions.append(f"monitor_before_strategy_change:{row['validation']}:{row['details']}")
    if closed_count < 30:
        actions.append("collect_more_closed_trades_before_trusting_edge")
    if not actions:
        actions.append("no_validation_blocker_detected_keep_observing")
    return actions


def _overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = [str(row.get("status")) for row in checks]
    if "DANGEROUS" in statuses:
        return "DANGEROUS"
    if "WARNING" in statuses:
        return "WARNING"
    return "SAFE"


def _status(value: float, *, warning: float, dangerous: float) -> str:
    if value >= dangerous:
        return "DANGEROUS"
    if value >= warning:
        return "WARNING"
    return "SAFE"


def _status_rank(status: str) -> int:
    return {"SAFE": 0, "WARNING": 1, "DANGEROUS": 2}.get(status, 0)


def _max_drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)
    return max_dd


def _first_datetime(row: dict[str, Any], keys: tuple[str, ...]) -> datetime | None:
    for key in keys:
        parsed = _parse_datetime(str(row.get(key) or ""))
        if parsed is not None:
            return parsed
    return None


def _dedupe_candle_time(value: object) -> datetime | None:
    text = str(value or "")
    for part in text.split("|"):
        parsed = _parse_datetime(part)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _score_bucket(value: object) -> str:
    score = _float(value)
    if score is None:
        return "UNKNOWN"
    if score < 60:
        return "<60"
    if score < 70:
        return "60-69"
    if score < 80:
        return "70-79"
    if score < 90:
        return "80-89"
    return "90+"


def _finite_pf(value: object) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if number > 100:
        return 100.0
    return number


def _rounded(value: object) -> float | str:
    number = _float(value)
    return "unknown" if number is None else round(number, 4)


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _confidence(sample_size: int) -> str:
    if sample_size >= 100:
        return "HIGH"
    if sample_size >= 30:
        return "MEDIUM"
    return "LOW"


def _pf(value: object) -> object:
    return "inf" if value is None else value


def _format_matrix(rows: Any) -> list[str]:
    if not isinstance(rows, list) or not rows:
        return ["- no validations"]
    return [
        f"- {row.get('validation')}: {row.get('status')} | {row.get('metric')}={row.get('value')} | {row.get('details')}"
        for row in rows
        if isinstance(row, dict)
    ]


def _format_list(values: list[str]) -> list[str]:
    return [f"- {value}" for value in values] if values else ["- none"]
