.DEFAULT_GOAL := all

install:
	pip install -U pip wheel
	pip install -e ".[opt]"

.PHONY: install-dev
install-dev:
	pip install -e ".[dev,ai,opt]"
	python -m pre-commit install
	python -m pre-commit autoupdate

.PHONY: lint
lint:
	python -m ruff check
	python -m ruff format --check

.PHONY: fmt
fmt:
	python -m ruff check --fix
	python -m ruff format


.PHONY: clean
clean:
	rm -rf `find . -name __pycache__`
	rm -rf output/
	rm -rf .ruff_cache/
	rm -rf *.egg-info
