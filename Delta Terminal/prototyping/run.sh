#!/usr/bin/env bash
# Open Bloomberg Terminal launcher
set -e
cd "$(dirname "$0")"

# Optional: pass AISHub username for global ship AIS
# export AISHUB_USERNAME=your_username

python main.py
