#!/usr/bin/env bash

pip install -r requirements.txt
playwright install chromium
python download_fonts.py
