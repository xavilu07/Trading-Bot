from trading_signals.app.settings import Settings
from trading_signals.application.use_cases.backtest_strategy import backtest_strategy
from tests.fixtures.market_data import generate_backtest_dataset


def test_backtest_generates_trades(tmp_path) -> None:
    settings = Settings(data_storage_path=tmp_path)
    result = backtest_strategy(generate_backtest_dataset(), "BTCUSDT", settings)
    assert result["total_trades"] > 0
