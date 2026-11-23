#!/usr/bin/env bash
# One command for the whole UI suite: boots the three dev API servers the web tests need, runs vitest, cleans up.
#   8123 plain dev API      -> tests/journey.test.tsx
#   8124 arms + probes on   -> tests/arms.test.tsx
#   8125 synthetic study    -> tests/admin.test.tsx
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
PIDS=()
cleanup() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done; rm -rf "$TMP"; }
trap cleanup EXIT
cd "$ROOT/apps/api"
LIMITS="RATE_PER_IP_PER_MIN=1000000 RATE_PER_SESSION_PER_MIN=1000000"
python -m vani.simulate --n 40 --db "sqlite:///$TMP/syn.db" > /dev/null
start() { # port, extra env...
  local port="$1"; shift
  env VANI_DEV=1 $LIMITS "$@" DATABASE_URL="sqlite:///$TMP/db$port.db" python -m uvicorn vani.app:create_app --factory --port "$port" --log-level warning > "$TMP/$port.log" 2>&1 &
  PIDS+=("$!")
}
start 8123
start 8124 ARMS_ENABLED=1 PROBES_ENABLED=1 PROBE_RATE=0.5
env VANI_DEV=1 DATABASE_URL="sqlite:///$TMP/syn.db" python -m uvicorn vani.app:create_app --factory --port 8125 --log-level warning > "$TMP/8125.log" 2>&1 &
PIDS+=("$!")
for port in 8123 8124 8125; do
  for _ in $(seq 1 40); do curl -sf "localhost:$port/healthz" > /dev/null && break; sleep 0.5; done
  curl -sf "localhost:$port/healthz" > /dev/null || { echo "API on $port did not start"; cat "$TMP/$port.log"; exit 1; }
done
cd "$ROOT/apps/web"
NEXT_PUBLIC_DEV=1 NEXT_PUBLIC_API_URL=http://127.0.0.1:8123 ARMS_API_URL=http://127.0.0.1:8124 ADMIN_API_URL=http://127.0.0.1:8125 npx vitest run "$@"
