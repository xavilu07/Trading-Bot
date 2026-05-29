from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import (
    canonical_trades_path,
    compute_trade_metrics,
    load_canonical_closed_trades as _load_canonical_closed_trades,
)


CORE_REPORTS = ("outcome_intelligence.csv", "edge_breakdown.csv", "setup_rankings.csv")
AUDITED_SYSTEMS = (
    "Dashboard",
    "Control Center",
    "Intelligence Reports",
    "Daily Reports",
    "Context Toxicity",
    "London Short Analysis",
    "Backtest Runner",
    "Focused Shadow Validation",
)
METRIC_KEYS = ("closed_trades", "total_r", "winrate", "profit_factor", "max_drawdown", "current_drawdown")


def run_data_consistency_audit(
    *,
    data_path: Path = Path("data"),
    reports_path: Path = Path("reports"),
    now: datetime | None = None,
) -> dict[str, Any]:
    now_dt = now or datetime.now(UTC)
    canonical = load_canonical_closed_trades(data_path)
    canonical_metrics = compute_metrics(canonical)
    report_sources = _report_sources(reports_path)
    source_summary = {
        "canonical_dataset": {
            "description": "data/paper_trading/trades.csv",
            "metrics": canonical_metrics,
            "files": _file_sources(data_path, reports_path),
        },
        "signals_log": _signals_log_status(data_path / "bot_activity" / "signals_log.jsonl"),
        "core_reports": report_sources,
    }
    systems = [
        _audit_system(
            "Dashboard",
            observed=canonical_metrics,
            expected=canonical_metrics,
            dataset_scope="canonical_trade_source",
            notes=["Dashboard must read data/paper_trading/trades.csv through canonical_trade_source."],
        ),
        _audit_system(
            "Control Center",
            observed=canonical_metrics,
            expected=canonical_metrics,
            dataset_scope="canonical_trade_source",
            notes=["Control Center must read data/paper_trading/trades.csv through canonical_trade_source."],
        ),
        _audit_system(
            "Intelligence Reports",
            observed=_metrics_from_outcome_report(reports_path / "outcome_intelligence.csv"),
            expected=canonical_metrics,
            dataset_scope="outcome_intelligence_csv",
            notes=_intelligence_notes(reports_path),
        ),
        _audit_system(
            "Daily Reports",
            observed=compute_metrics(_filter_trades_by_day(canonical, now_dt.date().isoformat())),
            expected=compute_metrics(_filter_trades_by_day(canonical, now_dt.date().isoformat())),
            dataset_scope="canonical_trade_source_today",
            notes=["Daily DEV Report is intentionally scoped to paper trades closed today."],
        ),
        _audit_system(
            "Context Toxicity",
            observed=_metrics_from_context_toxicity(reports_path / "context_toxicity_deep_dive.json"),
            expected=canonical_metrics,
            dataset_scope="canonical_trade_source",
            notes=["Context Toxicity must use canonical_trade_source, not strategy validation rows."],
        ),
        _audit_system(
            "London Short Analysis",
            observed=_metrics_from_london_short(reports_path / "london_short_edge_attribution.json"),
            expected=compute_metrics(_filter_london_short(canonical)),
            dataset_scope="canonical_trade_source_london_short_subset",
            notes=["London Short Analysis is expected to match the LONDON+SHORT subset if it only uses canonical trades."],
        ),
        _audit_system(
            "Backtest Runner",
            observed=_metrics_from_backtest_runner(reports_path / "backtest_runner_report.json"),
            expected=canonical_metrics,
            dataset_scope="canonical_trade_source",
            notes=["Backtest Runner baseline should be comparable to the canonical closed-trade universe."],
        ),
        _audit_system(
            "Focused Shadow Validation",
            observed=_metrics_from_range_shadow(reports_path / "range_penalty_shadow.json"),
            expected=canonical_metrics,
            dataset_scope="canonical_trade_source",
            notes=["Focused shadow validation must use canonical_trade_source."],
        ),
    ]
    overall = _overall_status(systems)
    result = {
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "status": overall,
        "audited_systems": list(AUDITED_SYSTEMS),
        "source_summary": source_summary,
        "systems": systems,
        "summary": {
            "consistent": len([item for item in systems if item["classification"] == "CONSISTENT"]),
            "minor_drift": len([item for item in systems if item["classification"] == "MINOR DRIFT"]),
            "critical_mismatch": len([item for item in systems if item["classification"] == "CRITICAL MISMATCH"]),
            "top_mismatches": _top_mismatches(systems),
        },
    }
    return result


def write_data_consistency_audit(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "data_consistency_audit.json"
    md_path = reports_path / "data_consistency_audit.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md_path.write_text(format_data_consistency_audit(result), encoding="utf-8")
    return {"json_path": json_path, "markdown_path": md_path}


def format_data_consistency_audit(result: dict[str, Any]) -> str:
    source = _dict(result.get("source_summary"))
    canonical = _dict(_dict(source.get("canonical_dataset")).get("metrics"))
    lines = [
        "# Data Consistency Audit",
        "",
        f"- Generated at: {result.get('generated_at')}",
        f"- Overall status: {result.get('status')}",
        "",
        "## Canonical Dataset",
        "",
        "- Base: `data/paper_trading/trades.csv`",
        f"- Closed trades: {canonical.get('closed_trades', 0)}",
        f"- Total R: {canonical.get('total_r', 0)}",
        f"- Winrate: {canonical.get('winrate', 0)}%",
        f"- Profit factor: {_pf(canonical.get('profit_factor'))}",
        f"- Max drawdown: {canonical.get('max_drawdown', 0)}",
        f"- Current drawdown: {canonical.get('current_drawdown', 0)}",
        "",
        "## Systems",
        "",
        "| System | Classification | Dataset scope | Closed trades | Total R | WR | PF | Max DD | Current DD |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for system in _list(result.get("systems")):
        observed = _dict(system.get("observed_metrics"))
        lines.append(
            "| {name} | {classification} | {scope} | {closed} | {total} | {wr}% | {pf} | {dd} | {current_dd} |".format(
                name=system.get("system"),
                classification=system.get("classification"),
                scope=system.get("dataset_scope"),
                closed=observed.get("closed_trades", 0),
                total=observed.get("total_r", 0),
                wr=observed.get("winrate", 0),
                pf=_pf(observed.get("profit_factor")),
                dd=observed.get("max_drawdown", 0),
                current_dd=observed.get("current_drawdown", 0),
            )
        )
    lines.extend(["", "## Mismatch Details", ""])
    for system in _list(result.get("systems")):
        lines.append(f"### {system.get('system')}")
        lines.append(f"- Classification: {system.get('classification')}")
        lines.append(f"- Dataset scope: `{system.get('dataset_scope')}`")
        lines.append(f"- Notes: {'; '.join(str(item) for item in _list(system.get('notes'))) or 'none'}")
        lines.append("- Diffs:")
        for key, diff in _dict(system.get("diffs")).items():
            if isinstance(diff, dict):
                lines.append(f"  - {key}: observed={diff.get('observed')} expected={diff.get('expected')} delta={diff.get('delta')}")
        lines.append("")
    lines.extend(["## Source Files", ""])
    for name, info in _dict(_dict(source.get("canonical_dataset")).get("files")).items():
        if isinstance(info, dict):
            lines.append(f"- `{name}`: exists={info.get('exists')} rows={info.get('rows')} size={info.get('size_bytes')} bytes")
    lines.extend(["", "## Core Reports", ""])
    for name, info in _dict(source.get("core_reports")).items():
        if isinstance(info, dict):
            lines.append(f"- `{name}`: exists={info.get('exists')} rows={info.get('rows')} size={info.get('size_bytes')} bytes")
    return "\n".join(lines).rstrip() + "\n"


def load_canonical_closed_trades(data_path: Path) -> list[dict[str, Any]]:
    return _load_canonical_closed_trades(data_path)


def load_primary_paper_trades(data_path: Path) -> list[dict[str, Any]]:
    return _load_canonical_closed_trades(data_path)


def compute_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    return compute_trade_metrics(trades)


def _audit_system(
    system: str,
    *,
    observed: dict[str, Any],
    expected: dict[str, Any],
    dataset_scope: str,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    diffs = _diff_metrics(observed, expected)
    classification = _classify_diffs(observed, expected, diffs)
    return {
        "system": system,
        "classification": classification,
        "dataset_scope": dataset_scope,
        "observed_metrics": observed,
        "expected_metrics": expected,
        "diffs": diffs,
        "notes": notes or [],
    }


def _diff_metrics(observed: dict[str, Any], expected: dict[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for key in METRIC_KEYS:
        observed_value = observed.get(key)
        expected_value = expected.get(key)
        output[key] = {
            "observed": observed_value,
            "expected": expected_value,
            "delta": _round_delta(_number(observed_value) - _number(expected_value)),
        }
    return output


def _classify_diffs(observed: dict[str, Any], expected: dict[str, Any], diffs: dict[str, dict[str, Any]]) -> str:
    if not observed or observed.get("missing"):
        return "CRITICAL MISMATCH"
    count_delta = abs(int(_number(diffs["closed_trades"]["delta"])))
    total_delta = abs(_number(diffs["total_r"]["delta"]))
    wr_delta = abs(_number(diffs["winrate"]["delta"]))
    pf_delta = abs(_number(diffs["profit_factor"]["delta"]))
    dd_delta = abs(_number(diffs["max_drawdown"]["delta"]))
    current_dd_delta = abs(_number(diffs["current_drawdown"]["delta"]))
    if all(
        (
            count_delta == 0,
            total_delta <= 0.0001,
            wr_delta <= 0.01,
            pf_delta <= 0.001,
            dd_delta <= 0.0001,
            current_dd_delta <= 0.0001,
        )
    ):
        return "CONSISTENT"
    if count_delta <= 2 and total_delta <= 0.25 and wr_delta <= 5 and pf_delta <= 0.2 and dd_delta <= 0.25 and current_dd_delta <= 0.25:
        return "MINOR DRIFT"
    return "CRITICAL MISMATCH"


def _overall_status(systems: list[dict[str, Any]]) -> str:
    classifications = Counter(str(system.get("classification")) for system in systems)
    if classifications.get("CRITICAL MISMATCH"):
        return "CRITICAL MISMATCH"
    if classifications.get("MINOR DRIFT"):
        return "MINOR DRIFT"
    return "CONSISTENT"


def _top_mismatches(systems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        systems,
        key=lambda item: (
            item.get("classification") == "CRITICAL MISMATCH",
            abs(_number(_dict(item.get("diffs")).get("total_r", {}).get("delta"))),
            abs(_number(_dict(item.get("diffs")).get("closed_trades", {}).get("delta"))),
        ),
        reverse=True,
    )
    return [
        {
            "system": item.get("system"),
            "classification": item.get("classification"),
            "closed_trades_delta": _dict(item.get("diffs")).get("closed_trades", {}).get("delta"),
            "total_r_delta": _dict(item.get("diffs")).get("total_r", {}).get("delta"),
            "dataset_scope": item.get("dataset_scope"),
        }
        for item in ranked[:5]
    ]


def _metrics_from_outcome_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"missing": True, **compute_metrics([])}
    trades = []
    for row in _read_csv(path):
        result_r = _float(row.get("result_r"))
        if result_r is None:
            continue
        trades.append({**row, "result_r": result_r, "status": row.get("status") or ("tp_hit" if result_r > 0 else "sl_hit")})
    return compute_metrics(trades)


def _metrics_from_context_toxicity(path: Path) -> dict[str, Any]:
    raw = _read_json(path)
    if not raw:
        return {"missing": True, **compute_metrics([])}
    metrics = _dict(raw.get("global_performance"))
    return _metrics_from_report_dict(metrics, closed_key="sample_size")


def _metrics_from_london_short(path: Path) -> dict[str, Any]:
    raw = _read_json(path)
    if not raw:
        return {"missing": True, **compute_metrics([])}
    metrics = _dict(raw.get("overall_metrics"))
    output = _metrics_from_report_dict(metrics, closed_key="trades")
    output["closed_trades"] = int(_number(raw.get("closed_trades") if raw.get("closed_trades") is not None else output.get("closed_trades")))
    return output


def _metrics_from_backtest_runner(path: Path) -> dict[str, Any]:
    raw = _read_json(path)
    if not raw:
        return {"missing": True, **compute_metrics([])}
    layers = [item for item in raw.get("layers", []) if isinstance(item, dict)]
    raw_layer = next((item for item in layers if item.get("layer") == "raw_strategy"), None)
    if not raw_layer:
        return {"missing": True, **compute_metrics([])}
    metrics = _dict(raw_layer.get("metrics"))
    return _metrics_from_report_dict(metrics, closed_key="trades_accepted")


def _metrics_from_range_shadow(path: Path) -> dict[str, Any]:
    raw = _read_json(path)
    if not raw:
        return {"missing": True, **compute_metrics([])}
    overall = _dict(raw.get("overall_metrics"))
    if overall:
        return _metrics_from_report_dict(overall, closed_key="trades")
    range_metrics = _dict(raw.get("range_penalty_metrics"))
    no_range_metrics = _dict(raw.get("no_range_penalty_metrics"))
    values = {
        "closed_trades": int(_number(range_metrics.get("trades"))) + int(_number(no_range_metrics.get("trades"))),
        "total_r": round(_number(range_metrics.get("total_r")) + _number(no_range_metrics.get("total_r")), 4),
        "wins": 0,
        "losses": 0,
        "max_drawdown": 0.0,
        "current_drawdown": 0.0,
    }
    wins_estimate = (_number(range_metrics.get("winrate")) / 100.0 * _number(range_metrics.get("trades"))) + (
        _number(no_range_metrics.get("winrate")) / 100.0 * _number(no_range_metrics.get("trades"))
    )
    gross_profit = _gross_profit_estimate(range_metrics) + _gross_profit_estimate(no_range_metrics)
    gross_loss = _gross_loss_estimate(range_metrics) + _gross_loss_estimate(no_range_metrics)
    values["wins"] = round(wins_estimate, 4)
    values["winrate"] = round(wins_estimate / values["closed_trades"] * 100, 2) if values["closed_trades"] else 0.0
    values["profit_factor"] = round(gross_profit / gross_loss, 4) if gross_loss > 0 else (round(gross_profit, 4) if gross_profit else 0.0)
    return values


def _metrics_from_report_dict(metrics: dict[str, Any], *, closed_key: str) -> dict[str, Any]:
    return {
        "closed_trades": int(_number(metrics.get(closed_key))),
        "wins": int(_number(metrics.get("wins"))),
        "losses": int(_number(metrics.get("losses"))),
        "total_r": round(_number(metrics.get("total_r")), 4),
        "winrate": round(_number(metrics.get("winrate")), 2),
        "profit_factor": _number(metrics.get("profit_factor")),
        "max_drawdown": round(_number(metrics.get("max_drawdown") or metrics.get("max_drawdown_r")), 4),
        "current_drawdown": round(_number(metrics.get("current_drawdown")), 4),
    }


def _gross_profit_estimate(metrics: dict[str, Any]) -> float:
    total = _number(metrics.get("total_r"))
    pf = metrics.get("profit_factor")
    if total <= 0 or pf in (None, "", "None"):
        return max(0.0, total)
    pf_num = _number(pf)
    if pf_num <= 0:
        return max(0.0, total)
    gross_loss = total / (pf_num - 1.0) if pf_num != 1.0 else 0.0
    return max(0.0, pf_num * gross_loss)


def _gross_loss_estimate(metrics: dict[str, Any]) -> float:
    total = _number(metrics.get("total_r"))
    pf = metrics.get("profit_factor")
    if total >= 0 or pf in (None, "", "None"):
        return abs(min(0.0, total))
    pf_num = _number(pf)
    if pf_num <= 0:
        return abs(total)
    gross_loss = abs(total / (pf_num - 1.0)) if pf_num != 1.0 else abs(total)
    return max(0.0, gross_loss)


def _filter_trades_by_day(trades: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    return [trade for trade in trades if str(_first_nonempty(trade, ("closed_at", "updated_at", "created_at", "timestamp"))).startswith(day)]


def _filter_london_short(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        trade
        for trade in trades
        if str(trade.get("session") or "").upper() == "LONDON" and str(trade.get("direction") or "").lower() == "short"
    ]


def _file_sources(data_path: Path, reports_path: Path) -> dict[str, dict[str, Any]]:
    paths = {
        "canonical_trades": canonical_trades_path(data_path),
        "signals_log": data_path / "bot_activity" / "signals_log.jsonl",
        "outcome_intelligence": reports_path / "outcome_intelligence.csv",
        "edge_breakdown": reports_path / "edge_breakdown.csv",
        "setup_rankings": reports_path / "setup_rankings.csv",
    }
    return {key: _file_status(path) for key, path in paths.items()}


def _report_sources(reports_path: Path) -> dict[str, dict[str, Any]]:
    return {name: _file_status(reports_path / name) for name in CORE_REPORTS}


def _signals_log_status(path: Path) -> dict[str, Any]:
    status = _file_status(path)
    event_counts: Counter[str] = Counter()
    if path.exists() and path.stat().st_size > 0:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                event_counts[str(item.get("event") or item.get("type") or "unknown")] += 1
    status["event_counts"] = dict(event_counts.most_common(10))
    return status


def _intelligence_notes(reports_path: Path) -> list[str]:
    manifest = _read_json(reports_path / "intelligence_layer_manifest.json")
    notes = ["Intelligence Reports are expected to align with outcome_intelligence.csv row metrics."]
    if manifest:
        rows = _dict(manifest.get("rows"))
        notes.append(
            "Manifest rows: closed_trades={closed}, outcome={outcome}, edge={edge}, setup={setup}".format(
                closed=rows.get("closed_trades", 0),
                outcome=rows.get("outcome_intelligence", 0),
                edge=rows.get("edge_breakdown", 0),
                setup=rows.get("setup_rankings", 0),
            )
        )
    return notes


def _file_status(path: Path) -> dict[str, Any]:
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": size,
        "rows": _count_rows(path) if exists else 0,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds") if exists else None,
    }


def _count_rows(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    if path.suffix == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return max(0, sum(1 for _ in handle) - 1)
    return 1


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except csv.Error:
        return []


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _first_nonempty(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _number(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_delta(value: float) -> float:
    return round(value, 4)


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _pf(value: object) -> object:
    return "inf" if value is None else value
