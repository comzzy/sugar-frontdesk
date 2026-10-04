#!/usr/bin/env bash
# Start Sugar's front desk locally on :8090 (reads TINKER_API_KEY from the environment).
cd "$(dirname "$0")"
[ -f /tmp/sugar-app.pid ] && kill "$(cat /tmp/sugar-app.pid)" 2>/dev/null && sleep 1
nohup .venv/bin/uvicorn main:app --app-dir app --host 0.0.0.0 --port "${PORT:-8090}" > /tmp/sugar-app.log 2>&1 &
echo $! > /tmp/sugar-app.pid
