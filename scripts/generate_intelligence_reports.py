from __future__ import annotations

import argparse
import json
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


def generate_intelligence_reports(
    *,
    data_path: Path,
    reports_path: Path,
    min_trades: int = 1,
    dashboard_min_trades: int = 3,
) -> dict[str, object]:
    reports_path.mkdir(parents=True, exist_ok=True)
    outcome = generate_outcome_intelligence(data_path, reports_path)
    rankings = generate_setup_rankings(data_path, reports_path, min_trades=max(1, min_trades))
    performance = generate_performance_report(data_path, reports_path)
    edge_rows = _count_csv_rows(reports_path / "edge_breakdown.csv")
    dashboard_path = reports_path / "dashboard.html"
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
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
    manifest["refreshed_intelligence_reports"] = _refresh_existing_intelligence_reports(reports_path, manifest)
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
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
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
        report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _refresh_report_markdown(report_json.with_suffix(".md"), stale_warning_names)
        refreshed.append(str(report_json))
    return refreshed


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


def _refresh_report_markdown(path: Path, stale_warning_names: tuple[str, ...]) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    filtered = [line for line in lines if not any(name in line for name in stale_warning_names)]
    path.write_text("\n".join(filtered).rstrip() + "\n", encoding="utf-8")


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
