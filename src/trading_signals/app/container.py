from __future__ import annotations

from trading_signals.app.settings import load_settings
from trading_signals.infrastructure.logging.logger import configure_logger
from trading_signals.infrastructure.metrics.noop_metrics import NoopMetrics
from trading_signals.infrastructure.notifications.telegram_notifier import TelegramNotifier
from trading_signals.infrastructure.persistence.file_store import FileStore
from trading_signals.infrastructure.persistence.repositories import FileScanRunRepository, FileSignalRepository
from trading_signals.application.use_cases.paper_trading import PaperTradingStore
from trading_signals.application.use_cases.live_trading import LiveTradingStore
from trading_signals.application.use_cases.experimental_paper import ExperimentalSignalStore
from trading_signals.application.use_cases.modular_paper import ModularSignalStore
from trading_signals.application.use_cases.shadow_paper import ShadowSignalStore
from trading_signals.infrastructure.exchange.provider_factory import build_market_data_provider
from trading_signals.memory.pattern_store import PatternMemoryStore


def build_container() -> dict[str, object]:
    settings = load_settings()
    store = FileStore(settings.data_storage_path)
    return {
        "settings": settings,
        "logger": configure_logger(settings.log_level),
        "market_data": build_market_data_provider(settings),
        "scan_repo": FileScanRunRepository(store),
        "signal_repo": FileSignalRepository(store),
        "notifier": TelegramNotifier(
            settings.telegram_bot_token,
            settings.telegram_chat_ids,
            settings.telegram_users_file,
            settings.telegram_state_file,
            public_chat_id=settings.telegram_public_chat_id,
            dev_chat_id=settings.telegram_dev_chat_id,
            dev_chat_ids=settings.telegram_dev_chat_ids,
            allowed_private_chat_ids=settings.telegram_allowed_private_chat_ids,
        ),
        "diagnostics_store": FileStore(settings.diagnostics_path),
        "paper_trading_store": PaperTradingStore(settings.data_storage_path),
        "experimental_signal_store": ExperimentalSignalStore(settings.data_storage_path),
        "shadow_signal_store": ShadowSignalStore(settings.data_storage_path),
        "modular_signal_store": ModularSignalStore(settings.data_storage_path),
        "live_trading_store": LiveTradingStore(settings.data_storage_path),
        "pattern_memory_store": PatternMemoryStore(settings.data_storage_path),
        "metrics": NoopMetrics(),
    }
