from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from trading_signals.agents.implementation.change_policy import evaluate_auto_apply_policy, validate_change_paths
from trading_signals.agents.qic_runtime import atomic_write_json, atomic_write_text, read_json_safe, utc_now


DEFAULT_CHANGE_STORE = Path("data") / "qic" / "code_changes.json"


class CodeChangeManager:
    def __init__(
        self,
        *,
        project_root: Path = Path("."),
        store_path: Path = DEFAULT_CHANGE_STORE,
        backup_root: Path = Path("data") / "qic" / "change_backups",
        allowlist: list[str] | None = None,
        denylist: list[str] | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.store_path = store_path
        self.backup_root = backup_root
        self.allowlist = allowlist or ["src/trading_signals/agents", "src/trading_signals/application/use_cases", "tests", "scripts", "Planning", "reports/qic", "src/trading_signals/interfaces/frontend", "deploy/frontend"]
        self.denylist = denylist or [".env", ".env.*", "config/qic_telegram.json", "credentials", "wallets", "keys", "live_trading", "risk_plan", "position_sizing"]

    def create_change(
        self,
        *,
        proposal_id: str,
        risk_level: str,
        generated_files: dict[str, str],
        validation: dict[str, Any] | None = None,
        council_votes: dict[str, Any] | None = None,
        implementation_council_approved: bool = False,
        approval_source: str = "none",
    ) -> dict[str, Any]:
        files = sorted(generated_files)
        path_check = validate_change_paths(files, allowlist=self.allowlist, denylist=self.denylist)
        changed_lines = sum(_changed_line_count(self.project_root / path, content) for path, content in generated_files.items())
        digest = hashlib.sha256(json.dumps({"proposal_id": proposal_id, "files": generated_files}, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        change_id = f"change_{digest}"
        state = self._load()
        existing = state["changes"].get(change_id)
        if isinstance(existing, dict):
            existing.update(
                {
                    "risk_level": str(risk_level).upper(),
                    "validation": validation or existing.get("validation") or {},
                    "council_votes": council_votes or existing.get("council_votes") or {},
                    "implementation_council_approved": bool(implementation_council_approved),
                    "path_policy": path_check,
                    "generated_files": generated_files,
                    "diff_stats": {"files": len(files), "changed_lines": changed_lines},
                }
            )
            if existing.get("final_status") in {"prepared", "blocked", "blocked_path_policy"}:
                existing["final_status"] = "prepared" if path_check["allowed"] else "blocked_path_policy"
                existing.pop("blockers", None)
            self._save(state)
            return existing
        change = {
            "change_id": change_id,
            "proposal_id": proposal_id,
            "created_at": utc_now(),
            "risk_level": str(risk_level).upper(),
            "files_changed": files,
            "diff_stats": {"files": len(files), "changed_lines": changed_lines},
            "validation": validation or {"tests_passed": False, "static_checks_passed": False, "coverage_regression": None},
            "council_votes": council_votes or {},
            "implementation_council_approved": bool(implementation_council_approved),
            "approval_source": approval_source,
            "rollback_available": True,
            "path_policy": path_check,
            "generated_files": generated_files,
            "applied_at": None,
            "verification": {},
            "rollback_id": None,
            "final_status": "prepared" if path_check["allowed"] else "blocked_path_policy",
        }
        state["changes"][change_id] = change
        self._save(state)
        return change

    def list_changes(self) -> list[dict[str, Any]]:
        return sorted(self._load()["changes"].values(), key=lambda item: str(item.get("created_at")), reverse=True)

    def get(self, change_id: str) -> dict[str, Any] | None:
        item = self._load()["changes"].get(change_id)
        return item if isinstance(item, dict) else None

    def apply(
        self,
        change_id: str,
        *,
        auto: bool = False,
        manual_approval: bool = False,
        auto_apply_low_risk: bool = False,
        auto_apply_medium_risk: bool = False,
        live_trading_changes_allowed: bool = False,
        max_files: int = 8,
        max_changed_lines: int = 400,
    ) -> dict[str, Any]:
        state = self._load()
        change = state["changes"].get(change_id)
        if not isinstance(change, dict):
            return {"status": "not_found", "change_id": change_id}
        blockers = []
        if not change.get("path_policy", {}).get("allowed"):
            blockers.append("path_policy_blocked")
        policy = evaluate_auto_apply_policy(
            change,
            auto_apply_low_risk=auto_apply_low_risk,
            auto_apply_medium_risk=auto_apply_medium_risk,
            live_trading_changes_allowed=live_trading_changes_allowed,
            max_files=max_files,
            max_changed_lines=max_changed_lines,
        )
        if auto:
            blockers.extend(policy["blockers"])
        else:
            manual_policy = evaluate_auto_apply_policy(
                change,
                auto_apply_low_risk=True,
                auto_apply_medium_risk=True,
                live_trading_changes_allowed=live_trading_changes_allowed,
                max_files=max_files,
                max_changed_lines=max_changed_lines,
            )
            blockers.extend(
                item for item in manual_policy["blockers"] if item != "human_approval_required_for_high_risk"
            )
            if not manual_approval:
                blockers.append("human_approval_missing")
        if str(change.get("risk_level")) in {"HIGH", "EXTREME"} and not manual_approval:
            blockers.append("high_risk_requires_human_approval")
        if blockers:
            change["final_status"] = "blocked"
            change["blockers"] = sorted(set(blockers))
            self._save(state)
            return change
        backup_dir = self.backup_root / change_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        manifest = {"change_id": change_id, "created_at": utc_now(), "files": {}}
        for relative, content in (change.get("generated_files") or {}).items():
            target = self._resolve(relative)
            old = target.read_text(encoding="utf-8") if target.exists() else None
            backup_path = backup_dir / relative
            if old is not None:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(backup_path, old)
            manifest["files"][relative] = {
                "existed": old is not None,
                "before_sha256": _sha(old),
                "after_sha256": _sha(_written_content(content)),
            }
        atomic_write_json(backup_dir / "manifest.json", manifest)
        for relative, content in (change.get("generated_files") or {}).items():
            atomic_write_text(self._resolve(relative), content)
        change.update(
            {
                "applied_at": utc_now(),
                "approval_source": "auto_policy" if auto else "human",
                "final_status": "applied",
                "backup_path": str(backup_dir),
                "post_apply_hashes": {
                    relative: _sha(_written_content(content))
                    for relative, content in (change.get("generated_files") or {}).items()
                },
            }
        )
        self._save(state)
        return change

    def verify(self, change_id: str) -> dict[str, Any]:
        state = self._load()
        change = state["changes"].get(change_id)
        if not isinstance(change, dict):
            return {"status": "not_found", "change_id": change_id}
        mismatches = []
        for relative, expected in (change.get("post_apply_hashes") or {}).items():
            target = self._resolve(relative)
            current = _sha(target.read_text(encoding="utf-8") if target.exists() else None)
            if current != expected:
                mismatches.append(relative)
        verification = {"verified_at": utc_now(), "status": "verified" if not mismatches else "drifted", "mismatches": mismatches}
        change["verification"] = verification
        self._save(state)
        return verification

    def update_validation(self, change_id: str, validation: dict[str, Any]) -> dict[str, Any] | None:
        state = self._load()
        change = state["changes"].get(change_id)
        if not isinstance(change, dict):
            return None
        change["validation"] = {**(change.get("validation") or {}), **validation, "updated_at": utc_now()}
        self._save(state)
        return change

    def rollback(self, change_id: str, *, manual_approval: bool = False) -> dict[str, Any]:
        state = self._load()
        change = state["changes"].get(change_id)
        if not isinstance(change, dict):
            return {"status": "not_found", "change_id": change_id}
        if not manual_approval:
            return {"status": "blocked", "change_id": change_id, "blockers": ["human_approval_missing"]}
        verification = self.verify(change_id)
        if verification.get("status") == "drifted":
            return {"status": "blocked", "change_id": change_id, "blockers": ["post_apply_changes_detected"], "verification": verification}
        manifest = read_json_safe(Path(str(change.get("backup_path") or "")) / "manifest.json", {})
        if not manifest:
            return {"status": "blocked", "change_id": change_id, "blockers": ["backup_manifest_missing"]}
        backup_dir = Path(str(change["backup_path"]))
        for relative, metadata in (manifest.get("files") or {}).items():
            target = self._resolve(relative)
            if metadata.get("existed"):
                atomic_write_text(target, (backup_dir / relative).read_text(encoding="utf-8"))
            elif target.exists():
                target.unlink()
        rollback_id = f"rollback_{change_id}_{datetime_token()}"
        change.update({"rollback_id": rollback_id, "rolled_back_at": utc_now(), "final_status": "rolled_back"})
        self._save(state)
        return change

    def _resolve(self, relative: str) -> Path:
        target = (self.project_root / relative).resolve()
        if self.project_root not in target.parents and target != self.project_root:
            raise ValueError(f"path_outside_project:{relative}")
        return target

    def _load(self) -> dict[str, Any]:
        state = read_json_safe(self.store_path, {"schema_version": 1, "changes": {}})
        if not isinstance(state, dict):
            state = {"schema_version": 1, "changes": {}}
        state.setdefault("changes", {})
        return state

    def _save(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        atomic_write_json(self.store_path, state)


def _sha(content: str | None) -> str | None:
    return hashlib.sha256(content.encode("utf-8")).hexdigest() if content is not None else None


def _written_content(content: str) -> str:
    return content if content.endswith("\n") else content + "\n"


def _changed_line_count(path: Path, new_content: str) -> int:
    old_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    new_lines = new_content.splitlines()
    return abs(len(new_lines) - len(old_lines)) + sum(1 for left, right in zip(old_lines, new_lines) if left != right)


def datetime_token() -> str:
    return utc_now().replace(":", "").replace("-", "").replace("+", "_").replace(".", "")
