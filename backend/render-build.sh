#!/usr/bin/env bash
# exit on error
set -e

pip install -r requirements.txt

# Force Playwright to install Chromium in a persistent path on Render
export PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/.playwright
echo "Installing Chromium to $PLAYWRIGHT_BROWSERS_PATH..."
python -m playwright install chromium
python -m playwright install-deps chromium

python download_fonts.py
