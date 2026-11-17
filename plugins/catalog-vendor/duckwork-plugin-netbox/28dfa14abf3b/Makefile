.PHONY: test test-duckwork lint fmt doctor

PY ?= python3

test:
	$(PY) -m unittest discover -s tests -t . -v

test-duckwork:
	@test -n "$(DUCKWORK_AGENT_ROOT)" || (echo "set DUCKWORK_AGENT_ROOT to a duckwork-agent checkout" && exit 1)
	DUCKWORK_AGENT_ROOT=$(DUCKWORK_AGENT_ROOT) $(DUCKWORK_AGENT_ROOT)/venv/bin/python -m unittest tests.test_plugin_load -v

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff format .
	ruff check --fix .

doctor:
	duckwork plugins doctor . --ci
