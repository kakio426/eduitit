# Fortune Post-Deploy Checklist

## Required env flags
- `FORTUNE_ASYNC_STREAM_ENABLED=True`
- `FORTUNE_ASYNC_API_ENABLED=True`

## Smoke checks (run in order)
1. Health endpoint
   - `GET /health/` returns `200` and JSON with `"status": "ok"`.
2. Saju API basic success
   - Submit one valid request to `/fortune/api/` and confirm non-empty result.
3. Chat streaming
   - Send one message in `/fortune/chat/send/` and confirm streamed assistant response.
4. Rate limit enforcement
   - Repeat requests until `429` appears on protected endpoints.
5. OAuth sanity
   - Verify Kakao login callback and Naver login callback both complete.
6. Cache sanity
   - Confirm `createcachetable` succeeded and rate-limit behavior is consistent across workers.

## Fast rollback switches (3-minute path)
1. Disable async AI path first
   - `FORTUNE_ASYNC_STREAM_ENABLED=False`
   - `FORTUNE_ASYNC_API_ENABLED=False`
2. Redeploy and re-test `/health/` + login + one fortune request.
3. If still unstable, switch process command back to Gunicorn rollback line in `Procfile`.

## Incident note template
- Timestamp (KST):
- Deployment SHA:
- Symptom:
- First failing endpoint:
- Action taken:
- Final status:
