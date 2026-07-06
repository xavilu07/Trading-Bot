from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_rollback_plan(proposal: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    flags = [item.get("name") for item in plan.get("required_feature_flags") or [] if item.get("name")]
    return {
        "proposal_id": proposal.get("id"),
        "knowledge_item_id": proposal.get("knowledge_item_id"),
        "created_at": datetime.now(tz=UTC).isoformat(),
        "rollback_type": "feature_flag_disable",
        "steps": [
            f"Set {flags[0]}=false" if flags else "Disable feature flag",
            "Restart only after manual approval if runtime config requires it",
            "Verify QIC monitoring report returns to baseline behavior",
        ],
        "feature_flags": flags,
        "data_migration_required": False,
        "code_revert_required": False,
    }
