from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_dashboard import generate_dashboard
from scripts.generate_outcome_intelligence import generate_outcome_intelligence
from scripts.generate_performance_report import generate_performance_report
from scripts.generate_setup_rankings import generate_setup_rankings
from trading_signals.data.canonical_trade_source import canonical_trades_path
from trading_signals.research.bot_audit_ai import build_relaxation_shadow_status, format_relaxation_shadow_status_lines


def generate_intelligence_reports(
    *,
    data_path: Path,
    reports_path: Path,
    min_trades: int = 1,
    dashboard_min_trades: int = 3,
    run_datetime: datetime | None = None,
    bot_data_dir: Path | None = None,
) -> dict[str, object]:
    reports_path.mkdir(parents=True, exist_ok=True)
    run_datetime = run_datetime or datetime.now(UTC)
    if run_datetime.tzinfo is None:
        run_datetime = run_datetime.replace(tzinfo=UTC)
    bot_data_dir = bot_data_dir or Path(os.getenv("BOT_DATA_DIR", str(reports_path.parent))).resolve()
    previous_latest_daily = _latest_daily_report(reports_path)
    outcome = generate_outcome_intelligence(data_path, reports_path)
    rankings = generate_setup_rankings(data_path, reports_path, min_trades=max(1, min_trades))
    performance = generate_performance_report(data_path, reports_path)
    edge_rows = _count_csv_rows(reports_path / "edge_breakdown.csv")
    dashboard_path = reports_path / "dashboard.html"
    manifest = {
        "generated_at": run_datetime.astimezone(UTC).isoformat(timespec="seconds"),
        "data_sources": {
            "canonical_trades_path": str(canonical_trades_path(data_path)),
            "canonical_trades_rows": _count_csv_rows(canonical_trades_path(data_path)),
            "signals_log_rows": _count_lines(data_path / "bot_activity" / "signals_log.jsonl"),
            "pattern_memory_rows": _count_lines(data_path / "pattern_memory" / "patterns.jsonl"),
        },
        "reports": {
            "outcome_intelligence": outcome.get("output_path"),
            "setup_rankings": rankings.get("setup_rankings_path"),
            "setup_combinations_rankings": rankings.get("setup_combinations_rankings_path"),
            "edge_breakdown": performance.get("edge_breakdown_path"),
            "secondary_signal_breakdown": performance.get("secondary_signal_breakdown_path"),
            "performance_report": performance.get("report_path"),
            "dashboard": str(dashboard_path),
        },
        "rows": {
            "outcome_intelligence": len(outcome.get("rows", [])) if isinstance(outcome.get("rows"), list) else 0,
            "setup_rankings": len(rankings.get("single", [])) if isinstance(rankings.get("single"), list) else 0,
            "setup_combinations_rankings": len(rankings.get("combinations", [])) if isinstance(rankings.get("combinations"), list) else 0,
            "edge_breakdown": edge_rows,
            "closed_trades": performance.get("metrics", {}).get("total_trades", 0) if isinstance(performance.get("metrics"), dict) else 0,
        },
        "warnings": _missing_required_reports(reports_path),
    }
    manifest["relaxation_shadow_status"] = build_relaxation_shadow_status(data_path=data_path, reports_path=reports_path)
    daily_report = _write_daily_intelligence_report(
        manifest=manifest,
        data_path=data_path,
        reports_path=reports_path,
        run_datetime=run_datetime,
        bot_data_dir=bot_data_dir,
    )
    manifest["daily_report"] = daily_report
    manifest["refreshed_intelligence_reports"] = _refresh_existing_intelligence_reports(reports_path, manifest)
    audit = _write_generation_audit(
        data_path=data_path,
        reports_path=reports_path,
        bot_data_dir=bot_data_dir,
        run_datetime=run_datetime,
        chosen_daily_report_date=str(daily_report.get("date", "")),
        actual_output_path=Path(str(daily_report.get("markdown_path", ""))),
        report_written=bool(daily_report.get("report_md_written")),
        previous_latest_daily=previous_latest_daily,
    )
    manifest["generation_audit"] = audit
    manifest_path = reports_path / "intelligence_layer_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_dashboard(data_path, reports_path, min_trades=max(1, dashboard_min_trades))
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def format_manifest(manifest: dict[str, object]) -> str:
    rows = manifest.get("rows", {})
    warnings = manifest.get("warnings", [])
    if not isinstance(rows, dict):
        rows = {}
    if not isinstance(warnings, list):
        warnings = []
    return (
        "🧠 Intelligence Layer Reports\n"
        f"- Outcome rows: {rows.get('outcome_intelligence', 0)}\n"
        f"- Setup ranking rows: {rows.get('setup_rankings', 0)}\n"
        f"- Edge breakdown rows: {rows.get('edge_breakdown', 0)}\n"
        f"- Combination ranking rows: {rows.get('setup_combinations_rankings', 0)}\n"
        f"- Closed trades analyzed: {rows.get('closed_trades', 0)}\n"
        f"- Missing required reports: {len(warnings)}\n"
        f"- Manifest: {manifest.get('manifest_path')}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-intelligence-reports")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    parser.add_argument("--min-trades", type=int, default=1)
    parser.add_argument("--dashboard-min-trades", type=int, default=3)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_intelligence_reports(
        data_path=Path(args.data_path),
        reports_path=Path(args.reports_path),
        min_trades=args.min_trades,
        dashboard_min_trades=args.dashboard_min_trades,
        bot_data_dir=Path(os.getenv("BOT_DATA_DIR", ".")).resolve(),
    )
    print(format_manifest(result))
    return 0


def _missing_required_reports(reports_path: Path) -> list[str]:
    required = ("edge_breakdown.csv", "setup_rankings.csv", "outcome_intelligence.csv")
    return [f"Missing required file: {reports_path / name}" for name in required if not (reports_path / name).exists()]


def _refresh_existing_intelligence_reports(reports_path: Path, manifest: dict[str, object]) -> list[str]:
    intelligence_path = reports_path / "intelligence"
    if not intelligence_path.exists():
        return []
    stale_warning_names = (
        "reports/outcome_intelligence.csv",
        "reports/setup_rankings.csv",
        "reports/edge_breakdown.csv",
    )
    rows = manifest.get("rows", {})
    if not isinstance(rows, dict):
        rows = {}
    relaxation_shadow_status = manifest.get("relaxation_shadow_status")
    refreshed = []
    for report_json in sorted(intelligence_path.glob("**/report.json")):
        try:
            report = json.loads(report_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(report, dict):
            continue
        data_sources = report.setdefault("data_sources", {})
        if isinstance(data_sources, dict):
            data_sources["outcome_rows"] = rows.get("outcome_intelligence", 0)
            data_sources["setup_rankings_rows"] = rows.get("setup_rankings", 0)
            data_sources["edge_breakdown_rows"] = rows.get("edge_breakdown", 0)
            data_sources["warnings"] = _remove_stale_warnings(data_sources.get("warnings"), stale_warning_names)
        report["warnings"] = _remove_stale_warnings(report.get("warnings"), stale_warning_names)
        if isinstance(relaxation_shadow_status, dict):
            report["relaxation_shadow_status"] = relaxation_shadow_status
        report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _refresh_report_markdown(report_json.with_suffix(".md"), stale_warning_names, relaxation_shadow_status)
        refreshed.append(str(report_json))
    return refreshed


def _write_daily_intelligence_report(
    *,
    manifest: dict[str, object],
    data_path: Path,
    reports_path: Path,
    run_datetime: datetime,
    bot_data_dir: Path,
) -> dict[str, object]:
    date_key = run_datetime.date().isoformat()
    report_dir = reports_path / "intelligence" / "daily" / date_key
    report_dir.mkdir(parents=True, exist_ok=True)
    latest_trade_timestamp = _latest_trade_timestamp(data_path)
    latest_signal_timestamp = _latest_signal_timestamp(data_path)
    payload = {
        "report_type": "daily",
        "period": date_key,
        "generated_at": run_datetime.astimezone(UTC).isoformat(timespec="seconds"),
        "bot_data_dir": str(bot_data_dir),
        "data_sources": {
            **dict(manifest.get("data_sources", {}) if isinstance(manifest.get("data_sources"), dict) else {}),
            "latest_trade_timestamp": latest_trade_timestamp,
            "latest_signal_timestamp": latest_signal_timestamp,
        },
        "reports": manifest.get("reports", {}),
        "rows": manifest.get("rows", {}),
        "warnings": manifest.get("warnings", []),
        "relaxation_shadow_status": manifest.get("relaxation_shadow_status", {}),
    }
    json_path = report_dir / "report.json"
    md_path = report_dir / "report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_format_daily_intelligence_markdown(payload), encoding="utf-8")
    return {
        "date": date_key,
        "directory": str(report_dir),
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "report_json_written": json_path.exists(),
        "report_md_written": md_path.exists(),
    }


def _format_daily_intelligence_markdown(payload: dict[str, object]) -> str:
    rows = payload.get("rows", {})
    data_sources = payload.get("data_sources", {})
    warnings = payload.get("warnings", [])
    if not isinstance(rows, dict):
        rows = {}
    if not isinstance(data_sources, dict):
        data_sources = {}
    if not isinstance(warnings, list):
        warnings = []
    return "\n".join(
        [
            f"# Intelligence Report DAILY {payload.get('period')}",
            "",
            f"Generated: {payload.get('generated_at')}",
            f"BOT_DATA_DIR: {payload.get('bot_data_dir')}",
            "",
            "## Data Freshness",
            f"- Latest trade timestamp: {data_sources.get('latest_trade_timestamp') or 'N/A'}",
            f"- Latest signal timestamp: {data_sources.get('latest_signal_timestamp') or 'N/A'}",
            "",
            "## Intelligence Layer",
            f"- Closed trades analyzed: {rows.get('closed_trades', 0)}",
            f"- Outcome rows: {rows.get('outcome_intelligence', 0)}",
            f"- Setup ranking rows: {rows.get('setup_rankings', 0)}",
            f"- Edge breakdown rows: {rows.get('edge_breakdown', 0)}",
            f"- Combination ranking rows: {rows.get('setup_combinations_rankings', 0)}",
            "",
            "## Warnings",
            *([f"- {warning}" for warning in warnings] if warnings else ["- none"]),
            "",
        ]
    )


def _write_generation_audit(
    *,
    data_path: Path,
    reports_path: Path,
    bot_data_dir: Path,
    run_datetime: datetime,
    chosen_daily_report_date: str,
    actual_output_path: Path,
    report_written: bool,
    previous_latest_daily: dict[str, object] | None,
) -> dict[str, object]:
    latest_after = _latest_daily_report(reports_path)
    current_date = run_datetime.date().isoformat()
    previous_date = str((previous_latest_daily or {}).get("date") or "")
    stale_before = bool(previous_date and previous_date < current_date)
    stale_after = bool((latest_after or {}).get("date") and str((latest_after or {}).get("date")) < current_date)
    if stale_before and report_written:
        stale_reason = "previous_generator_refreshed_existing_daily_reports_but_did_not_create_current_run_date; fixed_this_run"
    elif stale_after:
        stale_reason = "current_daily_report_was_not_written"
    elif not previous_latest_daily:
        stale_reason = "no_previous_daily_report_found"
    else:
        stale_reason = "latest_daily_folder_is_current"
    audit = {
        "current_system_date": current_date,
        "generated_at": run_datetime.astimezone(UTC).isoformat(timespec="seconds"),
        "bot_data_dir": str(bot_data_dir),
        "data_path": str(data_path),
        "reports_path": str(reports_path),
        "latest_trade_timestamp": _latest_trade_timestamp(data_path),
        "latest_signal_timestamp": _latest_signal_timestamp(data_path),
        "chosen_daily_report_date": chosen_daily_report_date,
        "actual_output_path": str(actual_output_path),
        "report_md_written": bool(report_written),
        "previous_latest_daily_report": previous_latest_daily,
        "latest_daily_report_after_generation": latest_after,
        "latest_daily_folder_was_stale_before_generation": stale_before,
        "latest_daily_folder_is_stale_after_generation": stale_after,
        "stale_explanation": stale_reason,
    }
    path = reports_path / "intelligence_generation_audit.md"
    path.write_text(_format_generation_audit_markdown(audit), encoding="utf-8")
    audit["audit_path"] = str(path)
    return audit


def _format_generation_audit_markdown(audit: dict[str, object]) -> str:
    previous = audit.get("previous_latest_daily_report") if isinstance(audit.get("previous_latest_daily_report"), dict) else {}
    latest = audit.get("latest_daily_report_after_generation") if isinstance(audit.get("latest_daily_report_after_generation"), dict) else {}
    return "\n".join(
        [
            "# Intelligence Generation Audit",
            "",
            f"- current system date: {audit.get('current_system_date')}",
            f"- BOT_DATA_DIR: {audit.get('bot_data_dir')}",
            f"- data path: {audit.get('data_path')}",
            f"- reports path: {audit.get('reports_path')}",
            f"- latest trade timestamp: {audit.get('latest_trade_timestamp') or 'N/A'}",
            f"- latest signal timestamp: {audit.get('latest_signal_timestamp') or 'N/A'}",
            f"- chosen daily report date: {audit.get('chosen_daily_report_date')}",
            f"- actual output path: {audit.get('actual_output_path')}",
            f"- report.md written: {audit.get('report_md_written')}",
            f"- previous latest daily folder: {previous.get('date', 'N/A')} ({previous.get('path', 'N/A')})",
            f"- latest daily folder after generation: {latest.get('date', 'N/A')} ({latest.get('path', 'N/A')})",
            f"- stale before generation: {audit.get('latest_daily_folder_was_stale_before_generation')}",
            f"- stale after generation: {audit.get('latest_daily_folder_is_stale_after_generation')}",
            f"- why latest daily folder is stale: {audit.get('stale_explanation')}",
            "",
        ]
    )


def _latest_daily_report(reports_path: Path) -> dict[str, object] | None:
    daily_path = reports_path / "intelligence" / "daily"
    reports = sorted(daily_path.glob("*/report.md")) if daily_path.exists() else []
    if not reports:
        return None
    latest = reports[-1]
    return {"date": latest.parent.name, "path": str(latest), "exists": latest.exists()}


def _latest_trade_timestamp(data_path: Path) -> str:
    rows = _read_csv_rows(canonical_trades_path(data_path))
    return _latest_timestamp_from_rows(rows)


def _latest_signal_timestamp(data_path: Path) -> str:
    path = data_path / "bot_activity" / "signals_log.jsonl"
    latest = ""
    if not path.exists():
        return latest
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            timestamp = str(payload.get("timestamp") or payload.get("created_at") or "")
            if timestamp and timestamp > latest:
                latest = timestamp
    return latest


def _latest_timestamp_from_rows(rows: list[dict[str, str]]) -> str:
    keys = ("closed_at", "updated_at", "evaluated_at", "exit_time", "opened_at", "created_at", "timestamp")
    latest = ""
    for row in rows:
        for key in keys:
            timestamp = str(row.get(key) or "").strip()
            if timestamp:
                latest = max(latest, timestamp)
                break
    return latest


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="", errors="replace") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _remove_stale_warnings(value: object, stale_warning_names: tuple[str, ...]) -> list[str]:
    if not isinstance(value, list):
        return []
    output = []
    for item in value:
        text = str(item)
        if any(name in text for name in stale_warning_names):
            continue
        output.append(text)
    return output


def _refresh_report_markdown(path: Path, stale_warning_names: tuple[str, ...], relaxation_shadow_status: object = None) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    filtered = [line for line in lines if not any(name in line for name in stale_warning_names)]
    filtered = _without_relaxation_shadow_status_section(filtered)
    if isinstance(relaxation_shadow_status, dict):
        filtered.extend(["", "## Relaxation Shadow Status", ""])
        filtered.extend(format_relaxation_shadow_status_lines(relaxation_shadow_status))
    path.write_text("\n".join(filtered).rstrip() + "\n", encoding="utf-8")


def _without_relaxation_shadow_status_section(lines: list[str]) -> list[str]:
    output: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == "## Relaxation Shadow Status":
            skipping = True
            continue
        if skipping and line.startswith("## "):
            skipping = False
        if not skipping:
            output.append(line)
    return output


def _count_csv_files(path: Path) -> int:
    return len([item for item in path.glob("*.csv") if item.is_file()]) if path.exists() else 0


def _count_lines(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for line in handle if line.strip())


def _count_csv_rows(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return max(0, sum(1 for _ in handle) - 1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
