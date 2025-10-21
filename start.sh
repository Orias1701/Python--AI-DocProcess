#!/usr/bin/env bash
set -e

# Uvicorn picks PORT from env (Spaces sets it). HOST is 0.0.0.0 for external access.
# Workers=1 to keep memory predictable on small machines; tune up if needed.
exec uvicorn app:app --host "${HOST:-0.0.0.0}" --port "${PORT:-7860}" --workers 1
