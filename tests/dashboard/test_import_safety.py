from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_import_has_no_operational_initialization_or_filesystem_writes(tmp_path: Path) -> None:
    script = """
import json
import sys
import trading_signals.interfaces.dashboard_api.main
import trading_signals.dashboard.outcomes.projector
import trading_signals.dashboard.cli
blocked = [
    name for name in sys.modules
    if name in {
        "trading_signals.app.container",
        "trading_signals.application.use_cases.run_market_scan",
        "trading_signals.infrastructure.notifications.telegram",
    }
]
print(json.dumps(blocked))
"""
    env = dict(os.environ)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "DASHBOARD_BOT_ROOT": str(tmp_path),
            "DASHBOARD_DATA_ROOT": str(tmp_path / "data"),
            "DASHBOARD_REPORTS_ROOT": str(tmp_path / "reports"),
            "DASHBOARD_RUNTIME_ROOT": str(tmp_path / "runtime"),
        }
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "[]"
    assert list(tmp_path.iterdir()) == []
