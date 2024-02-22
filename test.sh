#!/bin/bash

source .venv/bin/activate

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

pytest -q --cov=src tests/
