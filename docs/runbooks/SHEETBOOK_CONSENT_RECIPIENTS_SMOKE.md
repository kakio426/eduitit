# Sheetbook Consent Recipients Smoke Runbook

작성일: 2026-03-01  
대상: `SB-013` 대량 수신자(150~300줄) 편집 UX 검증

## 1) 목적

- `consent_review` 화면에서 대량 수신자 입력 시 편집 동선이 끊기지 않는지 확인한다.
- 문제 줄 목록/미니맵/활성 줄/요약 문구가 입력 변경에 맞춰 즉시 갱신되는지 확인한다.

## 2) 자동 실행(권장 1회)

- 명령:
  - `python scripts/run_sheetbook_consent_smoke.py`
- 대량 300줄 예시:
  - `python scripts/run_sheetbook_consent_smoke.py --valid-count 240 --duplicate-count 30 --invalid-count 30 --output docs/handoff/smoke_sheetbook_consent_recipients_300_latest.json`
- 동작:
  - 220줄(정상 180, 중복 20, 형식 확인 20) seed 자동 준비
  - `--valid-count/--duplicate-count/--invalid-count`로 시나리오 크기 조정 가능
  - 데스크톱 + 태블릿(iPad Pro 11 에뮬레이션)에서 다음 항목 검증
    - 요약 문구/문제 패널/미니맵 마커 노출
    - 문제 줄 점프(버튼 + 미니맵 다중 샘플: 상단/중간/하단 + 밀집 구간)
    - 미니맵 밀집 구간 lane 분산(`minimap_lane_count>=2`) + 중복 위치 없음(`minimap_duplicate_lane_top_count=0`)
    - 맨 위/맨 아래 이동
    - 입력 변경 후 중복/형식 확인 수치 갱신
    - `확인 후 동의서 만들기` 제출 후 step1 리다이렉트
- 산출물:
  - `docs/handoff/smoke_sheetbook_consent_recipients_latest.json`
  - (옵션) `docs/handoff/smoke_sheetbook_consent_recipients_300_latest.json`

## 3) 수동 확인(운영 전 권장)

1. `consent_review`에서 150~300줄 입력 상태로 진입
2. 문제 줄이 밀집된 구간에서 미니맵 마커 클릭 정확도 확인
3. 빠른 이동(문제 줄 버튼/미니맵) 후 활성 줄 표시가 일치하는지 확인
4. 태블릿 실기기에서 소프트키보드 표시/숨김 시 레이아웃 깨짐 여부 확인

## 4) 판정 기준

- `PASS`
  - 문제 줄 탐색(버튼/미니맵 다중 샘플)과 활성 줄 표시가 일치
  - 요약 수치(입력/반영/중복/형식 확인)가 입력 후 즉시 갱신
  - step1 이동까지 정상 완료, 콘솔 에러 없음
- `FAIL`
  - 문제 줄 점프가 반복적으로 틀리거나 활성 줄이 어긋남
  - 마커/문제 목록이 누락되거나 입력 후 갱신 지연이 큼
  - 제출 이후 리다이렉트 실패 또는 콘솔 에러 발생
