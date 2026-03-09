# Teacher-First Service Shell Checklist (2026-03-08)

## Status
- Baseline complete on current branch: `noticegen`, `timetable`, `parentcomm`, `reservations`
- Phase C rollout on current branch: `consent`, `signatures`, `hwpxchat`, `textbooks`, `slidesmith`, `happy_seed` (validated)
- This checklist is the same-source-of-truth for teacher-first first-screen contract.

## Goal
대표 서비스 첫 화면을 `설명형 랜딩`이 아니라 `교사가 바로 일 시작하는 화면`으로 통일한다.

## First-Screen Contract
- 첫 화면의 주인공은 설명이 아니라 작업 영역이다.
- 주 액션은 1~3개까지만 전면 배치한다.
- 공유, 협업, 연동, 고급 설정, 운영 로그는 기본 접힘 또는 2차 위치로 내린다.
- 긴 단계 설명은 금지하고, 필요하면 `details`나 보조 도움말로 내린다.
- 결과 화면은 입력 화면과 같은 높이의 주 작업 구역 안에서 바로 이어져야 한다.
- 브랜드형 카피보다 교사가 하는 일 이름을 먼저 쓴다.

## Service Review Order
1. noticegen
- 바로 만들기 / 생성 결과 중심
- 설명 문구 최소화

2. timetable
- 양식 받기 / 파일 올리기 / 반영 내역 분리
- 단계 설명과 로그 안내 축소

3. parentcomm
- 오늘 할 일 / 새 쪽지 / 상담 / 알림장 흐름 재배치
- 탭 과밀도 축소

4. reservations
- 예약 만들기 / 날짜 이동 / 관리자 기능 분리
- 헤더 액션 밀도 축소

5. consent
- 새 동의서 만들기 / 상태 확인 먼저
- 업무 기준과 법령은 접힘 패널로 후퇴

6. signatures
- 서명 미리보기 / 이미지 저장 / 스타일 저장 먼저
- 홍보성 카피와 업셀 패널 축소

7. hwpxchat
- 업로드 / 변환 / 복사 흐름 먼저
- 사용 이유/방법 설명은 접힌 도움말로 후퇴

8. textbooks
- 새 자료 만들기 / 내 자료실 먼저
- 학생 입장 안내와 운영 설명은 보조 위치로 후퇴

9. slidesmith
- 편집기 / 미리보기 / 발표 시작이 첫 화면의 주인공
- 발표 흐름, PDF 안내 같은 보조 설명은 최소화

10. happy_seed
- 내 교실 목록 / 새 교실 만들기 먼저
- 설명서와 운영 설명은 보조 링크 수준으로 후퇴

## Verification
- `python manage.py check`
- 대상 앱 테스트
- 변경된 템플릿의 inline JS 문법 확인
- 첫 화면 기준 중복 CTA, 설명 과다, 관리 기능 전면 노출 여부 수동 점검
