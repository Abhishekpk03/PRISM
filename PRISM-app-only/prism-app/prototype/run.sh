#!/usr/bin/env bash
# PRISM prototype launcher. Binds 0.0.0.0 so the preview proxy can reach it.
set -e
cd "$(dirname "$0")"
python3 -c "import flask" 2>/dev/null || pip install -q flask
exec python3 app.py
