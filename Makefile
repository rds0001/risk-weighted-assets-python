.PHONY: test quality build check clean

test:
	python -m pytest

quality:
	python -m ruff check src tests tools

build:
	python -m build

check:
	python -m twine check dist/*
	python tools/validate_distribution.py dist

clean:
	python tools/clean_build.py
