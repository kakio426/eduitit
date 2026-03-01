# Handoff: 씨앗퀴즈 교사 UX 개선 (2026-02-28)

## 1. 요청 배경
- 교사 화면에서 씨앗퀴즈 운영 중 아래 4가지 문제가 확인됨.
1. 문제 생성 후 완료 인지가 직관적이지 않음 (alert 부재)
2. 범위/주제/학년 기본값이 `전체`가 아니라 방금 만든 문제가 안 보이는 경우 발생
3. 학생 대시보드와 문제 제작 화면이 한 화면에 섞여 산만함
4. 학생 정답 결과 분석 화면이 없음

추가 요청:
- 실패 시에도 즉시 원인 안내가 보여야 교사가 바로 수정 가능

---

## 2. 이번 턴 구현 완료 범위

### 2.1 생성 성공/실패 즉시 알림
- 성공 시:
  - 결과 배너 + 브라우저 `alert` 동시 노출
  - `신규 생성 n개 / 기존 갱신 n개` 포함
- 실패 시:
  - 서버 에러 partial 렌더 후 오류 요약 `alert` 노출
  - 최대 3개 오류 + `외 n건` 표시
  - 일반 네트워크 오류도 기본 `alert` 노출

적용 파일:
- `seed_quiz/templates/seed_quiz/teacher_dashboard.html`
- `seed_quiz/templates/seed_quiz/partials/csv_upload_result.html`

### 2.2 필터 기본값 `전체` 정렬
- 기본값 변경:
  - 범위: `all`
  - 주제: `all`(신규 옵션 추가)
  - 학년: `all`
- 서버 필터 파서/쿼리 수정:
  - 주제/학년 `all` 처리 시 필터 미적용
  - 생성/RAG 경로는 기존처럼 구체 주제/학년 사용 (all 허용 안 함)

적용 파일:
- `seed_quiz/views.py`
- `seed_quiz/templates/seed_quiz/teacher_dashboard.html`

### 2.3 학생 대시보드 화면 분리
- 신규 페이지 추가:
  - `/seed-quiz/class/<classroom_id>/student-dashboard/`
- 기능:
  - 배포 세트 선택
  - 학생 접속 URL + QR + 링크 복사
  - 실시간 입장/제출 현황(10초 갱신)
- 배포 완료 partial에서는 기존 인라인 모니터 대신
  - `학생 대시보드 열기` 버튼으로 분리 페이지 유도

적용 파일:
- `seed_quiz/urls.py`
- `seed_quiz/views.py`
- `seed_quiz/templates/seed_quiz/teacher_student_dashboard.html`
- `seed_quiz/templates/seed_quiz/partials/teacher_published.html`

### 2.4 정답 결과 분석 화면 신설
- 신규 페이지 추가:
  - `/seed-quiz/class/<classroom_id>/analysis/`
- 기능:
  - 전체 통계: 전체 학생/제출/평균점수/만점/제출률
  - 문항별 분석: 정답률, 선택지별 인원, 최다 오답
  - 학생별 결과표: 상태, 답변 수, 점수, 정답률, 최근 시각
- 세트 선택 가능 (배포/종료 세트 대상)

적용 파일:
- `seed_quiz/urls.py`
- `seed_quiz/views.py`
- `seed_quiz/templates/seed_quiz/teacher_result_analysis.html`

---

## 3. 테스트/검증 결과

실행 및 결과:
1. `python manage.py test seed_quiz.tests.test_teacher_flow seed_quiz.tests.test_student_flow`
   - 통과 (54 passed)
2. 신규 추가 테스트만 재확인:
   - `test_dashboard_default_filters_are_all`
   - `test_teacher_student_dashboard_returns_200`
   - `test_teacher_result_analysis_returns_200`
   - 통과
3. 단일 렌더 회귀 확인:
   - `test_dashboard_returns_200`
   - 통과

참고:
- `python manage.py test seed_quiz.tests` 전체는 120초 타임아웃으로 중간에 끊긴 로그가 1회 있었음.
- 이후 핵심 범위(teacher_flow + student_flow)로 재실행하여 정상 통과 확인함.

---

## 4. 변경 파일 목록 (핵심)
- `seed_quiz/views.py`
- `seed_quiz/urls.py`
- `seed_quiz/templates/seed_quiz/teacher_dashboard.html`
- `seed_quiz/templates/seed_quiz/partials/csv_upload_result.html`
- `seed_quiz/templates/seed_quiz/partials/teacher_published.html`
- `seed_quiz/templates/seed_quiz/teacher_student_dashboard.html` (신규)
- `seed_quiz/templates/seed_quiz/teacher_result_analysis.html` (신규)
- `seed_quiz/tests/test_teacher_flow.py`

---

## 5. 집에서 이어서 할 우선순위 TODO (추천)

### P1. 실패 알림을 “수정 지시형”으로 업그레이드
- 현재: 오류 문구 그대로 alert
- 추천: 규칙 기반 치환으로 바로 행동 지시
  - 예: `학년은 0~6` -> `학년 칸 값을 0~6으로 수정`
  - 예: `필수 헤더 누락` -> `첫 줄 헤더를 템플릿 순서로 복구`

대상:
- `seed_quiz/templates/seed_quiz/teacher_dashboard.html` (JS 함수 `showErrorAlertFromResultArea`)

### P2. 방금 저장한 세트 하이라이트
- 성공 후 은행 목록 리로드 시
  - 방금 생성된 세트 ID를 전달
  - 해당 카드 자동 스크롤 + 배경 강조

대상 후보:
- `seed_quiz/partials/csv_upload_result.html`
- `seed_quiz/partials/bank_browse.html`
- `seed_quiz/views.py` (`htmx_bank_browse`, 저장 응답 payload 확장)

### P3. 분석 화면 CSV 다운로드
- 문항별/학생별 표를 CSV로 export
- 학급 회고, 생활기록 근거 자료로 사용 가능

대상 후보:
- `seed_quiz/views.py` (download endpoint 1~2개 추가)
- `seed_quiz/urls.py`
- `seed_quiz/templates/seed_quiz/teacher_result_analysis.html` (다운로드 버튼)

### P4. 오답 기반 재출제
- 분석 화면에서 오답률 높은 문항을 선택해 신규 세트 생성
- 다음 차시 보강학습 자동화 포인트

---

## 6. 빠른 수동 점검 체크리스트
1. 교사 대시보드 첫 진입 시 범위/주제/학년이 모두 `전체`인지 확인
2. 붙여넣기 `문제 만들기` 성공 시 success alert 확인
3. 의도적 잘못된 형식 업로드 후 failure alert에 오류 요약이 뜨는지 확인
4. 배포 후 `학생 대시보드 열기` 새 탭 이동 확인
5. `정답 결과 분석 보기`에서 통계/문항별/학생별 표 노출 확인

---

## 7. 참고 URL 패턴
- 교사 제작 대시보드:
  - `/seed-quiz/class/<classroom_id>/dashboard/`
- 학생 대시보드(분리):
  - `/seed-quiz/class/<classroom_id>/student-dashboard/`
- 정답 결과 분석:
  - `/seed-quiz/class/<classroom_id>/analysis/`

