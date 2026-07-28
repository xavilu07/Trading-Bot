from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field

from trading_signals.dashboard.contracts import Availability, Canonicality


class SourceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    path_template: str
    format: str
    canonicality: Canonicality
    producer: str
    expected_freshness_seconds: int | None = Field(default=None, ge=1)
    read_strategy: str
    redaction: str
    configured_availability: str
    join_keys: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedSource:
    definition: SourceDefinition
    path: Path | None
    probe_path: Path | None
    availability: Availability
    safe_reference: str


@dataclass(frozen=True, slots=True)
class SourceProbe:
    source: ResolvedSource
    observed_at: datetime
    size_bytes: int | None


class SourceCatalog:
    def __init__(self, definitions: tuple[SourceDefinition, ...], variables: Mapping[str, Path | None]) -> None:
        self._definitions = definitions
        self._variables = dict(variables)

    @classmethod
    def load_default(cls, variables: Mapping[str, Path | None]) -> SourceCatalog:
        manifest_path = Path(__file__).with_name("sources.v1.json")
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        definitions = tuple(SourceDefinition.model_validate(item) for item in raw["sources"])
        names = [item.name for item in definitions]
        if len(names) != len(set(names)):
            raise ValueError("source manifest contains duplicate logical names")
        return cls(definitions, variables)

    @property
    def definitions(self) -> tuple[SourceDefinition, ...]:
        return self._definitions

    def resolve(self, name: str) -> ResolvedSource:
        definition = next((item for item in self._definitions if item.name == name), None)
        if definition is None:
            raise KeyError(name)
        return self._resolve_definition(definition)

    def resolved_sources(self) -> tuple[ResolvedSource, ...]:
        return tuple(self._resolve_definition(item) for item in self._definitions)

    def probe(self, source: ResolvedSource) -> SourceProbe:
        now = datetime.now(timezone.utc)
        if source.probe_path is None or source.availability in {
            Availability.DISABLED,
            Availability.NOT_CONFIGURED,
        }:
            return SourceProbe(source=source, observed_at=now, size_bytes=None)
        try:
            stat = source.probe_path.stat()
        except (FileNotFoundError, OSError):
            return SourceProbe(
                source=replace(source, availability=Availability.MISSING),
                observed_at=now,
                size_bytes=None,
            )
        observed_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return SourceProbe(source=source, observed_at=observed_at, size_bytes=stat.st_size)

    def _resolve_definition(self, definition: SourceDefinition) -> ResolvedSource:
        if definition.configured_availability == "disabled":
            return ResolvedSource(
                definition=definition,
                path=None,
                probe_path=None,
                availability=Availability.DISABLED,
                safe_reference=self._safe_reference(definition.name, None),
            )

        placeholders = self._placeholders(definition.path_template)
        values: dict[str, str] = {}
        allowed_roots: list[Path] = []
        for placeholder in placeholders:
            configured = self._variables.get(placeholder)
            if configured is None:
                return ResolvedSource(
                    definition=definition,
                    path=None,
                    probe_path=None,
                    availability=Availability.NOT_CONFIGURED,
                    safe_reference=self._safe_reference(definition.name, None),
                )
            resolved_variable = configured.expanduser().resolve(strict=False)
            values[placeholder] = str(resolved_variable)
            allowed_roots.append(
                resolved_variable.parent
                if placeholder in {"active_signal_log", "scheduler_lock"}
                else resolved_variable
            )

        rendered = definition.path_template.format(**values)
        path = Path(rendered).resolve(strict=False)
        probe_path = self._probe_prefix(path)
        if allowed_roots and not any(self._is_within(probe_path, root) for root in allowed_roots):
            raise ValueError(f"source {definition.name!r} resolves outside configured roots")

        availability = Availability.AVAILABLE if probe_path.exists() else Availability.MISSING
        return ResolvedSource(
            definition=definition,
            path=path,
            probe_path=probe_path,
            availability=availability,
            safe_reference=self._safe_reference(definition.name, path),
        )

    @staticmethod
    def _placeholders(template: str) -> tuple[str, ...]:
        names: list[str] = []
        for part in template.split("{")[1:]:
            name = part.split("}", 1)[0]
            if name:
                names.append(name)
        return tuple(names)

    @staticmethod
    def _probe_prefix(path: Path) -> Path:
        parts: list[str] = []
        for part in path.parts:
            if "*" in part or "?" in part or "[" in part:
                break
            parts.append(part)
        return Path(*parts) if parts else path

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    @staticmethod
    def _safe_reference(name: str, path: Path | None) -> str:
        material = f"{name}:{path if path is not None else 'unconfigured'}"
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
        return f"source:{name}#{digest}"
