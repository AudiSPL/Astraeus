#!/usr/bin/env bash
set -e
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_ephe.py        # no-op if the .se1 files are already present
uvicorn app.main:app --reload --port 8080
