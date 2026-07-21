from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from trading_signals.agents.implementation.change_policy import evaluate_auto_apply_policy
from trading_signals.agents.implementation.code_changes import CodeChangeManager
from trading_signals.agents.notification_center import QICNotificationCenter
from trading_signals.agents.qic_dashboard import build_qic_control_center
from trading_signals.agents.qic_runtime import atomic_write_json, atomic_write_text, utc_now


def run_demo(*, output_path: Path = Path("reports") / "qic") -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="qic-e2e-") as temp_name:
        root = Path(temp_name)
        project = root / "project"
        demo_file = project / "Planning" / "qic_demo.md"
        demo_file.parent.mkdir(parents=True)
        demo_file.write_text("baseline\n", encoding="utf-8")
        stages = [
            {"stage": "event", "status": "simulated", "event": "NEW_EDGE_CANDIDATE"},
            {"stage": "hypothesis", "status": "simulated", "conditions": ["documentation=qic_demo"]},
            {"stage": "ranking", "status": "simulated", "rank": 1},
            {"stage": "simulation", "status": "passed", "risk": "LOW"},
            {"stage": "debate", "status": "consensus", "votes": 6},
            {"stage": "proposal", "status": "approved_for_demo", "proposal_id": "demo_low_risk"},
        ]
        notifications = QICNotificationCenter(data_path=root / "data" / "qic", enabled=True, bot_token="demo", chat_ids=["demo"], dry_run=True)
        telegram = notifications.publish("NEW_CIO_PROPOSAL", title="Demo proposal", message="No external call is made.", dedupe_key="demo")
        stages.append({"stage": "telegram", "status": telegram["status"]})
        manager = CodeChangeManager(
            project_root=project,
            store_path=root / "data" / "qic" / "code_changes.json",
            backup_root=root / "data" / "qic" / "change_backups",
            allowlist=["Planning"],
            denylist=[".env"],
        )
        change = manager.create_change(
            proposal_id="demo_low_risk",
            risk_level="LOW",
            generated_files={"Planning/qic_demo.md": "validated low-risk demo\n"},
            validation={"tests_passed": True, "static_checks_passed": True, "coverage_regression": False},
            council_votes={"implementation": "ALLOW", "safety": "ALLOW", "tests": "ALLOW"},
            implementation_council_approved=True,
        )
        policy = evaluate_auto_apply_policy(change, auto_apply_low_risk=True)
        stages.append({"stage": "code_generation", "status": change["final_status"], "change_id": change["change_id"]})
        stages.append({"stage": "tests", "status": "passed"})
        stages.append({"stage": "implementation_council", "status": "approved"})
        applied = manager.apply(change["change_id"], auto=True, auto_apply_low_risk=True)
        stages.append({"stage": "auto_apply", "status": applied["final_status"]})
        rollback = manager.rollback(change["change_id"], manual_approval=True)
        stages.append({"stage": "rollback", "status": rollback["final_status"]})
        dashboard = build_qic_control_center(data_path=root / "data", reports_path=root / "reports")
        stages.append({"stage": "dashboard", "status": "updated", "actions_enabled": dashboard["actions_enabled"]})
        report = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "mode": "offline_dry_run",
            "status": "passed" if all(item["status"] not in {"failed", "blocked"} for item in stages) else "failed",
            "stages": stages,
            "policy": policy,
            "external_calls": 0,
            "production_modified": False,
            "final_demo_file": demo_file.read_text(encoding="utf-8"),
        }
    output_path.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_path / "end_to_end_demo.json", report)
    lines = ["# QIC End-to-End Demo", "", f"- status: {report['status']}", f"- external_calls: {report['external_calls']}", f"- production_modified: {report['production_modified']}", "", "## Stages", ""]
    lines.extend(f"- {item['stage']}: {item['status']}" for item in stages)
    atomic_write_text(output_path / "end_to_end_demo.md", "\n".join(lines) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a reproducible offline QIC end-to-end demo.")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.parse_args(argv)
    report = run_demo()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
