# ArtClass Classroom UI Smoke Checklist

## Goal
- 교실 화면(`artclass/classroom`)의 텍스트 잘림, 도크 과밀, 버튼 접근성 문제를 빠르게 검증한다.
- 런처 코드 변경 없이 웹 UI만으로 16:9 / 4:3 / 9:16 대응 상태를 점검한다.

## Scope
- 대상 화면: `GET /artclass/classroom/<pk>/`
- 검증 포인트:
1. 단계 본문 가독성
2. 영상 하단 메타 도크(준비물/교사 팁) 동작
3. 하단 컨트롤(이전/일시정지/다음/자동전환) 접근성
4. TV Class Mode 토글 동작

## Test Matrix
- 해상도:
1. `1920x1080` (기준)
2. `1366x768` (저해상도)
3. `2560x1440` 이상 (고해상도)
- 비율 시뮬레이션:
1. `?video_profile=16x9`
2. `?video_profile=4x3`
3. `?video_profile=9x16`

예시:
- `/artclass/classroom/123/?video_profile=16x9`
- `/artclass/classroom/123/?video_profile=4x3`
- `/artclass/classroom/123/?video_profile=9x16`

## Pre-check
1. `python manage.py check` 통과
2. 브라우저 콘솔 `ReferenceError` 0건
3. 수업 데이터에 최소 3개 단계, 준비물/교사팁 포함 단계 1개 이상

## Scenario A: Embed Mode
1. 수업 시작 후 현재 단계 텍스트가 우측 패널에서 줄바꿈/스크롤로 정상 표시되는지 확인
2. 준비물/교사 팁이 영상 하단 도크로 이동되어 표시되는지 확인
3. 준비물/교사 팁이 없는 단계로 이동 시 도크 안내 문구가 보이는지 확인
4. `이전/다음/일시정지` 버튼이 항상 클릭 가능하고 레이블이 깨지지 않는지 확인
5. `TV Class Mode` 헤더 클릭 시 패널 펼침/접힘이 정상인지 확인

Pass criteria:
- 본문 핵심 문장이 잘리지 않음
- 도크가 플레이어 위를 덮지 않음
- 하단 버튼이 뷰포트 밖으로 밀려나지 않음

## Scenario B: External Window Mode
1. `playbackMode=external_window` 또는 `?autostart_launcher=1`로 진입
2. 좌측 영상 패널 숨김 상태에서 우측 본문에 준비물/교사 팁이 inline으로 표시되는지 확인
3. 메타 도크가 숨김 처리되는지 확인

Pass criteria:
- 메타 정보가 사라지지 않고 우측 본문으로 폴백됨
- 런처 실패 시에도 버튼 무반응 상태가 없음

## Scenario C: Dashboard Mode
1. `?display=dashboard&runtime=launcher`로 진입
2. 상단 헤더 숨김, 교사용 읽기 가독 모드(`dashboard-reading-mode`)가 유지되는지 확인
3. TV Class Mode 토글과 핵심 컨트롤이 동작하는지 확인

Pass criteria:
- 대시보드 전용 모드에서 화면 요소 충돌 없음
- 본문/컨트롤이 세로 스크롤 없이 조작 가능

## Known Aspect-Ratio Risks
1. `9:16` 영상은 좌우 레터박스가 커져 정보 밀도가 급격히 높아질 수 있음
2. `4:3` 영상은 상하 여백이 줄어 도크 높이 설정이 과하면 플레이어 체감 높이가 낮아질 수 있음
3. 저해상도(`1366x768`)에서는 본문/도크/컨트롤 간 세로 경쟁이 커짐

Mitigation check:
1. `ui-density-compact` 클래스가 적용되어 타이포/도크 높이가 축소되는지 확인
2. `video-profile-*` 클래스 전환에 따라 도크 높이가 조정되는지 확인

## Regression Checklist
1. `설명 수정` 패널 열기/저장/초기화가 기존대로 동작
2. `구간 반복` 버튼 상태 전환 정상
3. 런처 시작 버튼/새 창 열기 버튼 동작 정상
4. 자동 전환 타이머 진행 및 다음 단계 이동 정상
