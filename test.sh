#!/bin/bash

source .venv/bin/activate

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# remove unused imports first
isort -sl .
autoflake --remove-all-unused-imports -i -r .
isort .

pytest -q --cov=src tests/ $@
