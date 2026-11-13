#!/bin/sh
# PRISM launcher for macOS. Double-click this file in Finder.
cd "$(dirname "$0")" || exit 1
python3 run.py
printf '\nThe server has stopped. Press Return to close.\n'
read -r _
