from __future__ import annotations

from datetime import UTC, datetime

from trading_signals.domain.entities.market_snapshot import MarketSnapshot
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.scan_run import ScanRun
from trading_signals.domain.entities.signal_delivery import SignalDelivery
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.domain.entities.system_error import SystemError
from trading_signals.domain.entities.trade_signal import TradeSignal
from trading_signals.infrastructure.persistence.file_store import FileStore
from trading_signals.infrastructure.persistence.serializers import to_dict


def _date_key(timestamp: str | None = None) -> str:
    if timestamp:
        return timestamp[:10]
    return datetime.now(tz=UTC).date().isoformat()


class FileScanRunRepository:
    def __init__(self, store: FileStore) -> None:
        self.store = store

    def save_scan_run(self, run: ScanRun) -> None:
        self.store.write_json("scan_runs", _date_key(run.started_at), run.id, to_dict(run))

    def save_snapshot(self, snapshot: MarketSnapshot) -> None:
        self.store.write_json("market_snapshots", _date_key(snapshot.timestamp), snapshot.id, to_dict(snapshot))

    def save_evaluation(self, evaluation: StrategyEvaluation) -> None:
        self.store.write_json("strategy_evaluations", _date_key(evaluation.created_at), evaluation.id, to_dict(evaluation))

    def save_risk_plan(self, risk_plan: RiskPlan) -> None:
        self.store.write_json("risk_plans", _date_key(risk_plan.created_at), risk_plan.id, to_dict(risk_plan))

    def save_error(self, error: SystemError) -> None:
        self.store.write_json("system_errors", _date_key(error.created_at), error.id, to_dict(error))


class FileSignalRepository:
    def __init__(self, store: FileStore) -> None:
        self.store = store

    def save_signal(self, signal: TradeSignal) -> None:
        self.store.write_json("trade_signals", _date_key(signal.created_at), signal.id, to_dict(signal))

    def save_delivery(self, delivery: SignalDelivery) -> None:
        self.store.write_json("signal_deliveries", _date_key(delivery.attempted_at), delivery.id, to_dict(delivery))

    def list_latest_signals(self, limit: int = 20) -> list[dict[str, object]]:
        return self.store.list_json("trade_signals", limit=limit)

    def get_signal(self, signal_id: str) -> dict[str, object] | None:
        return self.store.read_json("trade_signals", signal_id)

    def has_published_dedupe_key(self, dedupe_key: str) -> bool:
        for item in self.store.list_json("trade_signals", limit=500):
            if item.get("dedupe_key") == dedupe_key and item.get("published_at"):
                return True
        return False
