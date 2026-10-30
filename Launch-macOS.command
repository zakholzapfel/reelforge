#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3.11 or later first. See README.md."
  exit 1
fi
if [ ! -f .venv/bin/python ]; then
  python3 -m venv .venv
fi
if [ ! -f .venv/reelforge-ready-0.5.0 ]; then
  .venv/bin/python -m pip install -e .
  touch .venv/reelforge-ready-0.5.0
fi
exec .venv/bin/python -m reelforge

