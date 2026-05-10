from __future__ import annotations

import json
import sys
from pathlib import Path

from trading_signals.app.settings import load_settings
from trading_signals.application.use_cases.backtest_strategy import backtest_strategy

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.fixtures.market_data import generate_trend_dataset
from tests.fixtures.market_data import generate_backtest_dataset


if __name__ == "__main__":
    settings = load_settings()
    dataset = generate_backtest_dataset(rows=320)
    print(json.dumps(backtest_strategy(dataset, "BTCUSDT", settings), indent=2, ensure_ascii=False))
