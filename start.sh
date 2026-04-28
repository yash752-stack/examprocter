#!/usr/bin/env bash
set -euo pipefail

uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
}

trap cleanup EXIT

streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
