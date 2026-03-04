#!/bin/bash
set -e
cd /Users/hwabaek/.openclaw/workspace/apps/market-brief-dashboard
/usr/bin/python3 scripts/update_data.py >/tmp/market-dashboard-update.log 2>&1 || exit 0
git add data/dashboard_data.json
if ! git diff --cached --quiet; then
  git commit -m "chore: auto-update dashboard data" >/tmp/market-dashboard-git.log 2>&1 || true
  git push >/tmp/market-dashboard-push.log 2>&1 || true
fi
