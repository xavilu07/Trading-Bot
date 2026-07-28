from __future__ import annotations

from pathlib import Path

import pytest

from trading_signals.dashboard.contracts import Availability, Canonicality
from trading_signals.dashboard.ingestion import SourceCatalog, SourceDefinition


def _variables(root: Path) -> dict[str, Path | None]:
    return {
        "bot_root": root,
        "data_root": root / "data",
        "reports_root": root / "reports",
        "runtime_root": root / "runtime",
        "active_signal_log": None,
        "scheduler_lock": None,
    }


def test_manifest_contains_all_audited_logical_sources(tmp_path: Path) -> None:
    catalog = SourceCatalog.load_default(_variables(tmp_path))
    names = {item.name for item in catalog.definitions}
    assert len(names) == 32
    assert {
        "scheduler_heartbeat",
        "scan_runs",
        "market_snapshots",
        "strategy_evaluations",
        "trade_signals",
        "paper_trades",
        "candidate_funnel",
        "signal_activity_active",
        "qic_system_health",
        "binance_market",
    } <= names


def test_release_relative_sources_require_explicit_configuration(tmp_path: Path) -> None:
    catalog = SourceCatalog.load_default(_variables(tmp_path))
    assert catalog.resolve("signal_activity_active").availability is Availability.NOT_CONFIGURED
    assert catalog.resolve("scheduler_lock").availability is Availability.NOT_CONFIGURED
    manifest_text = Path(
        "src/trading_signals/dashboard/ingestion/sources.v1.json"
    ).read_text(encoding="utf-8")
    assert "trading-bot-releases" not in manifest_text
    assert "451474c1d0bfd85fb5f590ac9aec9d6c2aee8a05" not in manifest_text


def test_source_resolution_stays_within_configured_root(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    definition = SourceDefinition(
        name="escape",
        path_template="{data_root}/../../outside.json",
        format="json",
        canonicality=Canonicality.CANONICAL,
        producer="test",
        read_strategy="bounded_json",
        redaction="all",
        configured_availability="required",
    )
    catalog = SourceCatalog((definition,), {"data_root": data_root})
    with pytest.raises(ValueError, match="outside configured roots"):
        catalog.resolve("escape")


def test_directory_root_with_suffix_is_not_treated_as_a_file(tmp_path: Path) -> None:
    data_root = tmp_path / "data.v1"
    definition = SourceDefinition(
        name="escape",
        path_template="{data_root}/../outside.json",
        format="json",
        canonicality=Canonicality.CANONICAL,
        producer="test",
        read_strategy="bounded_json",
        redaction="all",
        configured_availability="required",
    )
    catalog = SourceCatalog((definition,), {"data_root": data_root})
    with pytest.raises(ValueError, match="outside configured roots"):
        catalog.resolve("escape")


def test_safe_reference_does_not_expose_resolved_path(tmp_path: Path) -> None:
    heartbeat = tmp_path / "data/runtime/scheduler_heartbeat.json"
    heartbeat.parent.mkdir(parents=True)
    heartbeat.write_text("{}", encoding="utf-8")
    catalog = SourceCatalog.load_default(_variables(tmp_path))
    resolved = catalog.resolve("scheduler_heartbeat")
    assert resolved.availability is Availability.AVAILABLE
    assert str(tmp_path) not in resolved.safe_reference
    assert resolved.safe_reference.startswith("source:scheduler_heartbeat#")


def test_external_market_source_is_disabled_in_foundation(tmp_path: Path) -> None:
    catalog = SourceCatalog.load_default(_variables(tmp_path))
    assert catalog.resolve("binance_market").availability is Availability.DISABLED
