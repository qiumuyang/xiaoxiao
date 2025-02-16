#!/bin/bash

set -e # Stop on errors

source .venv/bin/activate

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

print_center() {
    text="$1"
    width=$(($(tput cols) - 2))
    pad_l=$((($width - ${#text}) / 2))
    pad_r=$(($width - ${#text} - $pad_l))
    if ((pad_l < 0)); then pad_l=0; fi
    if ((pad_r < 0)); then pad_r=0; fi
    echo "$(printf "%${pad_l}s" | tr ' ' '=') $text $(printf "%${pad_r}s" | tr ' ' '=')"
}

print_center "Removing unused imports"
# remove unused imports first
isort --force-single-line-imports .
autoflake --remove-all-unused-imports -i -r .
isort .

print_center "Auto formatting code with yapf"
# auto format code with yapf, use parallel
yapf -i -r -p src/ tests/

pytest --cov=src tests/ "$@"
