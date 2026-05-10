from __future__ import annotations

from trading_signals.infrastructure.logging.logger import log_json


def log_module_diagnostic(logger, *, symbol: str, module: str, result: dict[str, object]) -> None:
    log_json(
        logger,
        "module_diagnostic",
        symbol=symbol,
        module=module,
        ok=result.get("ok"),
        score=result.get("score"),
        reason=result.get("reason"),
        details=result.get("details", {}),
    )

