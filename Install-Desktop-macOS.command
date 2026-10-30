#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3.11 or later, then run this setup again. See README.md."
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or later is required."'
if [ ! -f .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -e ".[desktop]"
.venv/bin/python scripts/install_desktop.py
echo "ReelForge is in your home Applications folder. You can pin it to the Dock."
