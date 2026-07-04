from __future__ import annotations

from typing import Any

from trading_signals.research.statistics import to_float


CORE_FEATURES = (
    "symbol",
    "direction",
    "setup",
    "strategy",
    "session",
    "utc_hour",
    "market_regime",
    "location",
    "entry_zone",
    "score_bucket",
    "rr_bucket",
    "volume_ratio_bucket",
    "rsi_bucket",
    "bos",
    "liquidity_sweep",
    "liquidity_distance_bucket",
    "htf_alignment",
    "ltf_alignment",
    "holding_candles_bucket",
    "status",
)

NUMERIC_FEATURES = (
    "score",
    "rr",
    "volume_ratio",
    "rsi",
    "liquidity_distance",
    "atr",
    "holding_candles",
    "holding_hours",
)


def extract_feature_names(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    available = {key for row in rows for key, value in row.items() if value not in (None, "", "UNKNOWN")}
    categorical = [feature for feature in CORE_FEATURES if feature in available]
    numeric = [feature for feature in NUMERIC_FEATURES if any(to_float(row.get(feature)) is not None for row in rows)]
    dynamic_categorical = sorted(
        feature
        for feature in available
        if feature not in set(categorical)
        and feature not in set(numeric)
        and feature not in {"result_r", "entry_reasons"}
        and _reasonable_cardinality(rows, feature)
    )
    return {
        "categorical": [*categorical, *dynamic_categorical],
        "numeric": numeric,
    }


def _reasonable_cardinality(rows: list[dict[str, Any]], feature: str) -> bool:
    values = {str(row.get(feature) or "") for row in rows if row.get(feature) not in (None, "")}
    if not values:
        return False
    return len(values) <= max(50, len(rows) // 2)
