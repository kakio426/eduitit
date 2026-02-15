#!/bin/bash
set -euo pipefail

if [ -z "${BASE_URL:-}" ]; then
  echo "ERROR: BASE_URL is required. Example: BASE_URL=https://eduitit.site"
  exit 1
fi

echo "=== Post-deploy Smoke Check ==="
echo "BASE_URL=${BASE_URL}"

echo "[1/3] Health endpoint"
HEALTH_BODY="$(curl -fsS "${BASE_URL}/health/")"
echo "${HEALTH_BODY}" | grep -q '"status"' || {
  echo "ERROR: /health/ response did not contain status key"
  exit 1
}
echo "  OK"

echo "[2/3] Async rollout flags reminder"
echo "  Ensure Railway env has:"
echo "    FORTUNE_ASYNC_STREAM_ENABLED=True"
echo "    FORTUNE_ASYNC_API_ENABLED=True"
echo "  (This script cannot read Railway env directly.)"

echo "[3/3] Manual checks required"
echo "  - Saju API success (/fortune/api/)"
echo "  - Chat stream success (/fortune/chat/send/)"
echo "  - Rate limit 429 behavior"
echo "  - Kakao/Naver OAuth callback"
echo "  - Cross-worker cache consistency"

echo "=== Smoke check finished ==="
