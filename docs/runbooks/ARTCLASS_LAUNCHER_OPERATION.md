# ArtClass Teacher Launcher Runbook

## Goal
교사가 `런처로 수업 시작` 버튼을 한 번 누르면 자동으로:

1. 왼쪽: YouTube 영상 창
2. 오른쪽: ArtClass 대시보드 창

이 열리도록 운영한다.

## Web integration points
- API: `POST /artclass/api/classroom/<pk>/launcher-start/`
- Classroom dashboard mode: `?display=dashboard&runtime=launcher`
- Header action: `런처로 수업 시작`

## Launcher install (teacher PC)
1. `desktop/teacher-launcher`에서 Windows installer 생성
2. 교사 PC에 설치
3. 설치 후 브라우저에서 프로토콜 실행 허용

## Teacher flow
1. Setup/Library에서 `수업 시작하기` 클릭
2. `?autostart_launcher=1`로 classroom 진입 후 런처 자동 실행
3. 런처가 좌/우 분할 창 자동 배치
4. 필요 시 classroom 헤더의 `런처로 수업 시작` 버튼으로 재실행

## Fallback
런처 호출 실패 시:
1. 기존 `화면 분할 시작` 버튼 사용
2. 필요 시 `Win + ← / Win + →` 보조 안내

## Validation checklist
1. 비임베드 유튜브 링크에서 좌측 영상 창 정상 재생
2. 우측 대시보드 단계 전환/타이머/반복 모드 정상
3. 런처 재호출 시 기존 창 재정렬 정상
