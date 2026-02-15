# Fortune Async Rollout Runbook

## Scope
- 대상: `fortune` 사주 API async 전환 플래그 롤아웃
- 플래그:
  - `FORTUNE_ASYNC_STREAM_ENABLED`
  - `FORTUNE_ASYNC_API_ENABLED`

## Baseline (Before Deploy)
1. 코드 기준점 확보
- `git status --short`
- 배포 커밋 SHA 기록

2. 로컬 검증
- `python manage.py check`
- `python manage.py test fortune.tests.test_deepseek_streaming fortune.tests.test_streaming_logic fortune.tests.test_hybrid_api -v 2`

3. 운영 기준값 기록 (직전 24시간)
- `5xx` 비율
- `429` 비율
- `/fortune/api/streaming/` p95
- `/fortune/api/` p95

## Rollout Steps
1. 1차: streaming만 활성화
- `FORTUNE_ASYNC_STREAM_ENABLED=True`
- `FORTUNE_ASYNC_API_ENABLED=False`

2. 30분 관찰
- 에러 로그: `SynchronousOnlyOperation`, stream disconnect, timeout
- 트래픽 지표: `5xx`, `429`, p95

3. 2차: API 활성화
- `FORTUNE_ASYNC_API_ENABLED=True`

4. 30분 관찰
- `/fortune/api/`, `/fortune/api/daily/`, 토픽 분석 응답 확인
- 캐시 hit/miss 정상 확인

## SLO Guardrail (Rollback Trigger)
- 10분 이상 `5xx > 2%`
- 10분 이상 `429` 급증(기준값 대비 2배 이상)
- 사주 API p95 2배 이상 증가
- 로그인/일반 페이지 영향 감지

## Immediate Rollback
1. 플래그 롤백 (가장 빠름)
- `FORTUNE_ASYNC_STREAM_ENABLED=False`
- `FORTUNE_ASYNC_API_ENABLED=False`

2. 코드 롤백
- 단계 커밋만 선택적으로 `git revert <sha>`

3. 서버 런타임 롤백 (필요 시)
- `Procfile`을 gunicorn rollback 라인으로 복귀 후 재배포

## Post-Rollout Checklist
- 사주 스트리밍 1회 성공
- 사주 API 1회 성공
- 일진 API 1회 성공
- 로그인/회원가입 정상
- Sentry 신규 치명 에러 없음

