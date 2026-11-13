#!/bin/sh
# Double-click this file in Finder. It starts the app and opens your browser.
cd "$(dirname "$0")/prototype" || exit 1
python3 run.py
printf '\nThe server has stopped. Press Return to close.\n'
read -r _
