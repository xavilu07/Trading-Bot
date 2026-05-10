from __future__ import annotations

from dataclasses import asdict, is_dataclass


def to_dict(value: object) -> dict[str, object]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return value
    raise TypeError(f"Unsupported value for serialization: {type(value)!r}")

