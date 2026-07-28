from __future__ import annotations

import hashlib
import json
from pathlib import Path

from trading_signals.dashboard.cli import main
from trading_signals.dashboard.metrics.projector import (
    MetricProjectionConfig,
    compare_cohorts,
    inspect_cohort,
    inspect_metric,
    project_metrics_once,
)
from trading_signals.dashboard.storage import (
    apply_migrations,
    connect_read_only,
    connect_writer,
    integrity_check,
)


def _seed_database(root: Path) -> MetricProjectionConfig:
    data_root = root / "data"
    data_root.mkdir()
    database = root / "runtime/read-model.sqlite"
    connection = connect_writer(database, data_root=data_root)
    apply_migrations(connection)
    now = "2026-07-28T13:00:00+00:00"
    connection.execute(
        """
        INSERT INTO source_metadata(
            logical_source_name, source_format, source_classification,
            availability, freshness_status, projector_version
        ) VALUES ('trade_signals','json','CANONICAL','AVAILABLE','FRESH','fixture')
        """
    )
    policy_json = json.dumps(
        {
            "policy_version": "closed-bars-entry-touch-v1",
            "engine_version": "canonical-outcomes.v1",
            "timeframe": "1h",
            "horizon_candles": 24,
            "entry_activation_policy": "REQUIRE_POST_DECISION_TOUCH",
            "collision_policy": "AMBIGUOUS",
            "require_contiguous_candles": True,
            "closed_candles_only": True,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    connection.execute(
        """
        INSERT INTO outcome_policies(
            policy_version,engine_version,timeframe,horizon_candles,
            entry_activation_policy,collision_policy,require_contiguous_candles,
            closed_candles_only,policy_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "closed-bars-entry-touch-v1",
            "canonical-outcomes.v1",
            "1h",
            24,
            "REQUIRE_POST_DECISION_TOUCH",
            "AMBIGUOUS",
            1,
            1,
            policy_json,
            now,
        ),
    )
    fingerprint = "d" * 64
    connection.execute(
        """
        INSERT INTO market_data_sources(
            market_data_fingerprint,logical_source_name,source_format,
            timeframe,candles_count,data_quality,source_reference,payload_json,
            registered_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            fingerprint,
            "market_snapshots",
            "json_files",
            "1h",
            24,
            "COMPLETE",
            "source:market_snapshots",
            "{}",
            now,
        ),
    )
    cases = (
        ("win", "long", "WIN", "COMPLETE", 1, "ELIGIBLE_RESOLVED", "RESOLVED_WIN"),
        ("loss", "short", "LOSS", "COMPLETE", 1, "ELIGIBLE_RESOLVED", "RESOLVED_LOSS"),
        ("expired", "long", "EXPIRED", "COMPLETE", 1, "ELIGIBLE_ACTIVATED", "ACTIVATED_EXPIRED"),
        ("not-active", "short", "EXPIRED", "COMPLETE", 0, "NOT_ACTIVATED", "ENTRY_NOT_ACTIVATED"),
        ("ambiguous", "long", "AMBIGUOUS", "COMPLETE", 1, "EXCLUDED_AMBIGUOUS", "UNRESOLVED_AMBIGUOUS"),
        ("missing", "short", "NO_MARKET_DATA", "GAP", 0, "EXCLUDED_NO_MARKET_DATA", "INSUFFICIENT_EVIDENCE"),
    )
    for index, (name, direction, status, quality, activated, eligibility, lifecycle) in enumerate(cases):
        projection = f"projection-{name}"
        timestamp = f"2026-07-{index + 1:02d}T10:00:00+00:00"
        connection.execute(
            """
            INSERT INTO signals(
                projection_key,signal_id,event_timestamp,symbol,direction,
                timeframe,setup,decision,status,strategy_version,policy_version,
                source_logical_name,source_record_identity,raw_payload_json,
                ingested_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                projection,
                name,
                timestamp,
                "BTCUSDT" if index < 3 else "ETHUSDT",
                direction,
                "1h",
                "MAIN_SIGNAL",
                direction,
                "valid",
                "v1",
                "runtime-v1",
                "trade_signals",
                name,
                "{}",
                now,
            ),
        )
        entry, stop, target = (
            (100.0, 95.0, 110.0)
            if direction == "long"
            else (100.0, 105.0, 90.0)
        )
        connection.execute(
            """
            INSERT INTO signal_outcomes(
                outcome_id,signal_projection_key,signal_id,symbol,direction,
                timeframe,entry_timestamp,entry_price,stop_price,target_price,
                candles_expected,candles_observed,terminal_status,data_quality,
                policy_version,engine_version,market_data_fingerprint,
                source_fingerprint,strategy_version,computed_at,entry_activated,
                entry_activation_candle_open,entry_activation_evidence_id,
                candles_until_entry,candles_after_entry,entry_lifecycle_status,
                eligibility_status,eligibility_reason
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                f"outcome-{name}",
                projection,
                name,
                "BTCUSDT" if index < 3 else "ETHUSDT",
                direction,
                "1h",
                timestamp,
                entry,
                stop,
                target,
                24,
                24 if status == "EXPIRED" else 3,
                status,
                quality,
                "closed-bars-entry-touch-v1",
                "canonical-outcomes.v1",
                fingerprint,
                fingerprint,
                "v1",
                now,
                activated,
                timestamp if activated else None,
                ("e" * 64) if activated else None,
                1 if activated else None,
                23 if activated else None,
                lifecycle,
                eligibility,
                eligibility,
            ),
        )
    connection.commit()
    connection.close()
    return MetricProjectionConfig(data_root=data_root, sqlite_path=database)


def test_metrics_projection_is_idempotent_and_preserves_data_root(tmp_path: Path) -> None:
    config = _seed_database(tmp_path)
    (config.data_root / "source-sentinel.json").write_text(
        '{"source":"unchanged"}',
        encoding="utf-8",
    )
    before = {
        str(path.relative_to(config.data_root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in config.data_root.rglob("*")
        if path.is_file()
    }
    first = project_metrics_once(config)
    second = project_metrics_once(config)
    assert first.outcomes_observed == 6
    assert first.entry_activated == 4
    assert first.eligible_resolved == 2
    assert first.eligible_activated_expired == 1
    assert first.already_present is False
    assert second.already_present is True
    assert second.cohorts_written == 0
    after = {
        str(path.relative_to(config.data_root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in config.data_root.rglob("*")
        if path.is_file()
    }
    assert before == after
    connection = connect_read_only(config.sqlite_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM metric_runs").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM metric_exclusions"
        ).fetchone()[0] == 2
        cohort_payload = json.loads(
            connection.execute(
                "SELECT cohort_json FROM metric_cohorts "
                "WHERE cohort_name='ELIGIBLE_RESOLVED' AND dimension_name IS NULL"
            ).fetchone()[0]
        )
        assert cohort_payload["sensitivity"]["leave_one_setup_out"]["status"] == (
            "INSUFFICIENT_SAMPLE"
        )
        assert cohort_payload["temporal_comparison_rule"].startswith("UTC entry month")
        assert integrity_check(connection) == ("ok",)
    finally:
        connection.close()


def test_inspection_commands_are_read_only_and_denominators_visible(tmp_path: Path) -> None:
    config = _seed_database(tmp_path)
    project_metrics_once(config)
    before = hashlib.sha256(config.sqlite_path.read_bytes()).hexdigest()
    metric = inspect_metric(config.sqlite_path, "resolved_win_rate")
    cohort = inspect_cohort(config.sqlite_path, "ELIGIBLE_RESOLVED")
    comparison = compare_cohorts(
        config.sqlite_path,
        "ELIGIBLE_RESOLVED_BY_DIRECTION",
        "ELIGIBLE_RESOLVED",
    )
    assert metric["status"] == "ok"
    assert all(item["denominator"] >= 0 for item in metric["items"])
    assert cohort["status"] == "ok"
    assert comparison["comparison_type"] == "descriptive_not_causal"
    assert hashlib.sha256(config.sqlite_path.read_bytes()).hexdigest() == before


def test_multiple_fingerprints_for_same_signal_are_excluded(tmp_path: Path) -> None:
    config = _seed_database(tmp_path)
    connection = connect_writer(config.sqlite_path, data_root=config.data_root)
    second_fingerprint = "f" * 64
    connection.execute(
        """
        INSERT INTO market_data_sources(
            market_data_fingerprint,logical_source_name,source_format,
            timeframe,candles_count,data_quality,source_reference,payload_json,
            registered_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            second_fingerprint,
            "market_snapshots",
            "json_files",
            "1h",
            24,
            "COMPLETE",
            "source:market_snapshots",
            "{}",
            "2026-07-28T13:00:00+00:00",
        ),
    )
    connection.execute(
        """
        INSERT INTO signal_outcomes(
            outcome_id,signal_projection_key,signal_id,symbol,direction,
            timeframe,entry_timestamp,entry_price,stop_price,target_price,
            candles_expected,candles_observed,terminal_status,data_quality,
            policy_version,engine_version,market_data_fingerprint,
            source_fingerprint,strategy_version,computed_at,entry_activated,
            entry_activation_candle_open,candles_until_entry,candles_after_entry,
            entry_lifecycle_status,eligibility_status,eligibility_reason
        )
        SELECT 'outcome-win-recomputed',signal_projection_key,signal_id,symbol,
               direction,timeframe,entry_timestamp,entry_price,stop_price,
               target_price,candles_expected,candles_observed,terminal_status,
               data_quality,policy_version,engine_version,?, ?,strategy_version,
               computed_at,entry_activated,entry_activation_candle_open,
               candles_until_entry,candles_after_entry,entry_lifecycle_status,
               eligibility_status,eligibility_reason
        FROM signal_outcomes WHERE outcome_id='outcome-win'
        """,
        (second_fingerprint, second_fingerprint),
    )
    connection.commit()
    connection.close()
    summary = project_metrics_once(config)
    assert summary.eligible_resolved == 1
    reader = connect_read_only(config.sqlite_path)
    try:
        assert reader.execute(
            "SELECT COUNT(*) FROM metric_exclusions "
            "WHERE reason_code='MULTIPLE_MARKET_FINGERPRINTS_FOR_SIGNAL'"
        ).fetchone()[0] == 2
    finally:
        reader.close()


def test_metrics_cli_is_finite_and_inspection_is_read_only(
    tmp_path: Path,
    capsys,
) -> None:
    config = _seed_database(tmp_path)
    args = [
        "--sqlite-path",
        str(config.sqlite_path),
        "--bot-root",
        str(tmp_path),
        "--data-root",
        str(config.data_root),
        "--reports-root",
        str(tmp_path / "reports"),
        "--runtime-root",
        str(tmp_path / "runtime"),
    ]
    assert main(["metrics-once", *args]) == 0
    projected = json.loads(capsys.readouterr().out)
    assert projected["summary"]["eligible_resolved"] == 2
    before = hashlib.sha256(config.sqlite_path.read_bytes()).hexdigest()
    assert main(["inspect-metric", *args, "--metric-name", "resolved_win_rate"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert main(["inspect-cohort", *args, "--cohort", "ELIGIBLE_RESOLVED"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert (
        main(
            [
                "compare-cohorts",
                *args,
                "--left-cohort",
                "ELIGIBLE_RESOLVED_BY_DIRECTION",
                "--right-cohort",
                "ELIGIBLE_RESOLVED",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["comparison_type"] == (
        "descriptive_not_causal"
    )
    assert hashlib.sha256(config.sqlite_path.read_bytes()).hexdigest() == before
