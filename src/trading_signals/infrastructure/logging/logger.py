from __future__ import annotations

import json
import logging
import sys


def configure_logger(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("trading_signals")
    if logger.handlers:
        return logger
    logger.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def log_json(logger: logging.Logger, event: str, **kwargs: object) -> None:
    payload = {"event": event, **kwargs}
    logger.info(json.dumps(payload, ensure_ascii=False))

