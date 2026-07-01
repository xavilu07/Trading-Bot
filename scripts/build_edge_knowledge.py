from __future__ import annotations

import argparse
from pathlib import Path

from trading_signals.intelligence.edge_knowledge import write_edge_knowledge


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = write_edge_knowledge(
        report_path=Path(args.report_path),
        output_path=Path(args.output_path),
        reports_path=Path(args.reports_path),
    )
    print("EDGE_KNOWLEDGE_BASE_V1")
    print(f"- Knowledge: {paths['knowledge']}")
    print(f"- Report JSON: {paths['json']}")
    print(f"- Report Markdown: {paths['markdown']}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="build-edge-knowledge")
    parser.add_argument("--report-path", default="reports/performance_intelligence_report_v2.json")
    parser.add_argument("--output-path", default="data/edge_knowledge/knowledge_v1.json")
    parser.add_argument("--reports-path", default="reports")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
