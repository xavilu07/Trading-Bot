PYTHON := .venv/bin/python
PIP := .venv/bin/pip
UVICORN := .venv/bin/uvicorn
PYTEST := .venv/bin/pytest

.PHONY: venv install test specs scan scheduler telegram-start telegram-listener diagnostics-summary module-diagnostics-summary experimental-signals-summary update-experimental-outcomes shadow-signals-summary update-shadow-outcomes experimental-outcomes-scheduler experimental-outcomes-up experimental-outcomes-down experimental-outcomes-status experimental-outcomes-logs api-up api-down api-status api-logs scheduler-up scheduler-down scheduler-status scheduler-logs

venv:
	python3 -m venv .venv

install:
	$(PIP) install -e '.[dev]'

test:
	$(PYTEST) -q

specs:
	$(PYTHON) scripts/check_specs.py

scan:
	$(PYTHON) -m trading_signals.app.cli scan --dry-run

scheduler:
	$(PYTHON) -m trading_signals.app.cli scheduler

telegram-start:
	$(PYTHON) -m trading_signals.app.cli telegram-start

telegram-listener:
	$(PYTHON) -m trading_signals.app.cli telegram-listener

diagnostics-summary:
	$(PYTHON) scripts/diagnostics_summary.py

module-diagnostics-summary:
	$(PYTHON) scripts/module_diagnostics_summary.py

experimental-signals-summary:
	$(PYTHON) scripts/experimental_signals_summary.py

update-experimental-outcomes:
	$(PYTHON) scripts/update_experimental_outcomes.py

shadow-signals-summary:
	$(PYTHON) scripts/shadow_signals_summary.py

update-shadow-outcomes:
	$(PYTHON) scripts/update_shadow_outcomes.py

experimental-outcomes-scheduler:
	$(PYTHON) scripts/experimental_outcomes_scheduler.py

experimental-outcomes-up:
	zsh scripts/experimental_outcomes_up.sh

experimental-outcomes-down:
	zsh scripts/experimental_outcomes_down.sh

experimental-outcomes-status:
	zsh scripts/experimental_outcomes_status.sh

experimental-outcomes-logs:
	zsh scripts/experimental_outcomes_logs.sh

scheduler-up:
	zsh scripts/scheduler_up.sh

scheduler-down:
	zsh scripts/scheduler_down.sh

scheduler-status:
	zsh scripts/scheduler_status.sh

scheduler-logs:
	zsh scripts/scheduler_logs.sh

api-up:
	zsh scripts/dev_up.sh

api-down:
	zsh scripts/dev_down.sh

api-status:
	zsh scripts/dev_status.sh

api-logs:
	zsh scripts/dev_logs.sh
