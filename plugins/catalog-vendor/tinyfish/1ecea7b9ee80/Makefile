.PHONY: all format lint test clean

all: format lint test

format:
	ruff format tinyfish_duckwork tests
	ruff check --fix tinyfish_duckwork tests

lint:
	ruff check tinyfish_duckwork tests
	mypy tinyfish_duckwork

test:
	pytest tests -v

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
