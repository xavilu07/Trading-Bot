from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _optional_path(name: str) -> Path | None:
    value = os.getenv(name)
    return Path(value).expanduser().resolve(strict=False) if value else None


@dataclass(frozen=True, slots=True)
class DashboardSettings:
    bot_root: Path
    data_root: Path
    reports_root: Path
    runtime_root: Path
    read_model_path: Path | None = None
    active_signal_log: Path | None = None
    scheduler_lock: Path | None = None
    api_host: str = "127.0.0.1"
    api_port: int = 8101
    future_frontend_host: str = "127.0.0.1"
    future_frontend_port: int = 3101

    @classmethod
    def from_env(cls) -> DashboardSettings:
        bot_root = Path(os.getenv("DASHBOARD_BOT_ROOT", str(_REPOSITORY_ROOT))).expanduser().resolve(strict=False)
        data_root = Path(os.getenv("DASHBOARD_DATA_ROOT", str(bot_root / "data"))).expanduser().resolve(strict=False)
        reports_root = Path(os.getenv("DASHBOARD_REPORTS_ROOT", str(bot_root / "reports"))).expanduser().resolve(
            strict=False
        )
        runtime_root = Path(
            os.getenv("DASHBOARD_RUNTIME_ROOT", str(bot_root.parent / "trading-bot-runtime"))
        ).expanduser().resolve(strict=False)
        return cls(
            bot_root=bot_root,
            data_root=data_root,
            reports_root=reports_root,
            runtime_root=runtime_root,
            read_model_path=Path(
                os.getenv(
                    "DASHBOARD_READ_MODEL_PATH",
                    str(runtime_root / "dashboard-v2" / "read-model.sqlite"),
                )
            )
            .expanduser()
            .resolve(strict=False),
            active_signal_log=_optional_path("DASHBOARD_ACTIVE_SIGNAL_LOG"),
            scheduler_lock=_optional_path("DASHBOARD_SCHEDULER_LOCK"),
            api_host=os.getenv("DASHBOARD_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("DASHBOARD_API_PORT", "8101")),
            future_frontend_host=os.getenv("DASHBOARD_FRONTEND_HOST", "127.0.0.1"),
            future_frontend_port=int(os.getenv("DASHBOARD_FRONTEND_PORT", "3101")),
        )

    def source_variables(self) -> dict[str, Path | None]:
        return {
            "bot_root": self.bot_root,
            "data_root": self.data_root,
            "reports_root": self.reports_root,
            "runtime_root": self.runtime_root,
            "active_signal_log": self.active_signal_log,
            "scheduler_lock": self.scheduler_lock,
        }

    def resolved_read_model_path(self) -> Path:
        return (
            self.read_model_path
            or (self.runtime_root / "dashboard-v2" / "read-model.sqlite")
        ).expanduser().resolve(strict=False)
