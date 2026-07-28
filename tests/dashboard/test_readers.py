from __future__ import annotations

import os
from pathlib import Path

import pytest

from trading_signals.dashboard.ingestion.readers import (
    JsonlCheckpoint,
    SourceChangedError,
    SourceCorruptError,
    SourceSchemaError,
    read_csv_snapshot,
    read_json_snapshot,
    read_jsonl_increment,
)


def test_json_snapshot_valid_and_repeatable(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text('{"id":"one","status":"ok"}', encoding="utf-8")
    first, first_snapshot = read_json_snapshot(source)
    second, second_snapshot = read_json_snapshot(source)
    assert first == second == {"id": "one", "status": "ok"}
    assert first_snapshot.fingerprint == second_snapshot.fingerprint
    assert first_snapshot.source_identity == second_snapshot.source_identity


def test_json_snapshot_rejects_corrupt_document(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text('{"id":', encoding="utf-8")
    with pytest.raises(SourceCorruptError):
        read_json_snapshot(source)


def test_json_snapshot_detects_replacement_during_read(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text('{"id":"one"}', encoding="utf-8")
    calls = 0

    def replace(path: Path) -> None:
        nonlocal calls
        calls += 1
        replacement = path.with_suffix(".replacement")
        replacement.write_text(f'{{"id":"replacement-{calls}"}}', encoding="utf-8")
        os.replace(replacement, path)

    with pytest.raises(SourceChangedError):
        read_json_snapshot(source, retries=2, after_read=replace)


def test_jsonl_stops_before_partial_line_and_resumes_from_offset(tmp_path: Path) -> None:
    source = tmp_path / "events.jsonl"
    first_line = b'{"id":"one"}\n'
    source.write_bytes(first_line + b'{"id":"two"')
    first = read_jsonl_increment(source)
    assert first.records == ({"id": "one"},)
    assert first.next_byte_offset == len(first_line)
    with source.open("ab") as handle:
        handle.write(b"}\n")
    second = read_jsonl_increment(
        source,
        JsonlCheckpoint(
            first.source_identity,
            first.next_byte_offset,
            first.source_fingerprint,
        ),
    )
    assert second.records == ({"id": "two"},)
    assert second.next_byte_offset == source.stat().st_size


def test_jsonl_corrupt_line_does_not_advance_beyond_it(tmp_path: Path) -> None:
    source = tmp_path / "events.jsonl"
    valid = b'{"id":"one"}\n'
    source.write_bytes(valid + b'not-json\n' + b'{"id":"three"}\n')
    batch = read_jsonl_increment(source)
    assert batch.records == ({"id": "one"},)
    assert batch.next_byte_offset == len(valid)
    assert batch.error_code == "SOURCE_CORRUPT"


def test_jsonl_truncation_resets_invalid_checkpoint(tmp_path: Path) -> None:
    source = tmp_path / "events.jsonl"
    source.write_bytes(b'{"id":"one"}\n{"id":"two"}\n')
    first = read_jsonl_increment(source)
    source.write_bytes(b'{"id":"new"}\n')
    second = read_jsonl_increment(
        source,
        JsonlCheckpoint(first.source_identity, first.next_byte_offset),
    )
    assert second.reset_from_checkpoint is True
    assert second.records == ({"id": "new"},)


def test_jsonl_rotation_resets_identity_and_constraints_can_deduplicate(tmp_path: Path) -> None:
    source = tmp_path / "events.jsonl"
    source.write_bytes(b'{"id":"one"}\n')
    first = read_jsonl_increment(source)
    source.rename(tmp_path / "events.jsonl.1")
    source.write_bytes(b'{"id":"one"}\n{"id":"two"}\n')
    second = read_jsonl_increment(
        source,
        JsonlCheckpoint(first.source_identity, first.next_byte_offset),
    )
    assert second.reset_from_checkpoint is True
    assert second.source_identity != first.source_identity
    assert [record["id"] for record in second.records] == ["one", "two"]


def test_jsonl_prefix_fingerprint_detects_in_place_rewrite(tmp_path: Path) -> None:
    source = tmp_path / "events.jsonl"
    source.write_bytes(b'{"id":"one"}\n')
    first = read_jsonl_increment(source)
    with source.open("r+b") as handle:
        handle.write(b'{"id":"two"}\n')
    second = read_jsonl_increment(
        source,
        JsonlCheckpoint(
            first.source_identity,
            first.next_byte_offset,
            first.source_fingerprint,
        ),
    )
    assert second.reset_from_checkpoint is True
    assert second.records == ({"id": "two"},)


def test_jsonl_detects_replacement_during_read(tmp_path: Path) -> None:
    source = tmp_path / "events.jsonl"
    source.write_bytes(b'{"id":"one"}\n')

    def replace(path: Path) -> None:
        replacement = path.with_suffix(".new")
        replacement.write_bytes(b'{"id":"two"}\n')
        os.replace(replacement, path)

    with pytest.raises(SourceChangedError):
        read_jsonl_increment(source, after_read=replace)


def test_csv_snapshot_valid_and_repeatable(tmp_path: Path) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id,status\none,ok\ntwo,rejected\n", encoding="utf-8")
    first = read_csv_snapshot(source, required_columns=("id", "status"))
    second = read_csv_snapshot(source, required_columns=("id", "status"))
    assert first.rows == second.rows
    assert first.fingerprint == second.fingerprint


def test_csv_rejects_incompatible_header_and_partial_row(tmp_path: Path) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id\none\n", encoding="utf-8")
    with pytest.raises(SourceSchemaError):
        read_csv_snapshot(source, required_columns=("id", "status"))
    source.write_text("id,status\none\n", encoding="utf-8")
    with pytest.raises(SourceSchemaError):
        read_csv_snapshot(source, required_columns=("id", "status"))


def test_csv_detects_concurrent_modification(tmp_path: Path) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id,status\none,ok\n", encoding="utf-8")

    def append(path: Path) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("two,ok\n")

    with pytest.raises(SourceChangedError):
        read_csv_snapshot(
            source,
            required_columns=("id", "status"),
            retries=2,
            after_read=append,
        )
