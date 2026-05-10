from __future__ import annotations

import sys

from trading_signals.app.cli import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
