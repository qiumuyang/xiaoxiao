#!/bin/bash

source .venv/bin/activate

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# remove unused imports first
isort --force-single-line-imports .
autoflake --remove-all-unused-imports -i -r .
isort .

# auto format code with yapf
yapf -i -r src/ tests/

pytest -q --cov=src tests/ $@
