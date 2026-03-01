# 씨앗 퀴즈 교사 여정 QA 체크리스트 (2026-03-01)

## 범위
- 교사 핵심 여정: 생성 → 저장 → 미리보기 → 배포 → 학생/분석 화면 이동 → 교체/되돌리기
- PC/모바일 공통 가독성 및 버튼 동작 인지

## 체크리스트 결과
1. 대시보드 진입 시 안내 문구가 "AI 중심"으로 노출되고 구버전 3단계 문구가 보이지 않는다.
- 기대: `AI로 순식간에 퀴즈 만들기` 노출, `3단계로 끝나요` 제거
- 근거: `test_dashboard_returns_200`
- 상태: PASS

1-1. 대시보드 상단의 운영 이동 버튼이 새 탭 동작임을 명확히 보여준다.
- 기대: `운영 화면 열기 (새 탭)`, `학생 대시보드 (새 탭)`, `정답 분석 (새 탭)`
- 근거: `test_dashboard_shows_new_tab_navigation_labels`
- 상태: PASS

2. 붙여넣기 저장 시 성공 피드백과 "방금 만든 세트 열기" 동선이 제공된다.
- 기대: 성공 박스 + `data-open-latest-preview`
- 근거: `test_text_upload_save_mode_creates_bank_immediately`
- 상태: PASS

3. CSV 확인 저장 시에도 동일하게 자동 다음 동선이 제공된다.
- 기대: 성공 박스 + `data-open-latest-preview`
- 근거: `test_csv_confirm_auto_shares_as_public_approved`
- 상태: PASS

4. 저장된 문제 미리보기에서 운영 핵심 버튼 3종(배포/다른 세트/보관)이 상단에 있다.
- 기대: 질문 목록 위 버튼 배치, 로딩 인디케이터/중복 클릭 방지
- 근거: `seed_quiz/templates/seed_quiz/partials/teacher_preview.html`, `test_bank_select_creates_draft_preview`
- 상태: PASS

5. "다른 세트 고르기" 클릭 시 은행 목록으로 이동하고 다음 액션이 명확하다.
- 기대: 은행 영역 스크롤 + 첫 `이 세트 적용` 버튼 포커스
- 근거: `seed_quiz/templates/seed_quiz/teacher_dashboard.html` (JS: `data-seed-quiz-open-bank`)
- 상태: PASS

6. 배포 시 배포 완료 카드에서 학생/분석 이동 경로가 명확하고 새 탭 안내가 보인다.
- 기대: `학생 대시보드 열기 (새 탭)`, `정답 결과 분석 보기 (새 탭)`
- 근거: `seed_quiz/templates/seed_quiz/partials/teacher_published.html`, `test_publish_changes_status`
- 상태: PASS

7. 이미 배포 중일 때 교체 확인창의 취소가 "빈 화면"이 아니라 원래 미리보기로 복귀한다.
- 기대: 취소 버튼이 set preview endpoint 호출
- 근거: `test_publish_requires_force_and_closes_existing_published`, `htmx_set_preview`
- 상태: PASS

8. 교체 배포 후 직전 배포 복구(롤백)가 동작한다.
- 기대: 이전 세트 published 복원
- 근거: `test_publish_rollback_restores_previous_set`
- 상태: PASS

9. 배포 중 세트는 바로 보관되지 않고 안내 메시지로 보호된다.
- 기대: 409 + 안내 문구
- 근거: `test_set_archive_rejects_published_set`
- 상태: PASS

10. 학생 대시보드/정답 분석 화면도 새 탭 이동 문구가 일관적이다.
- 기대: `정답 분석 열기 (새 탭)`, `학생 대시보드 열기 (새 탭)`
- 근거: `test_teacher_student_dashboard_returns_200`, `test_teacher_result_analysis_returns_200`
- 상태: PASS

## 실행한 검증
- 전체 교사 흐름 테스트 실행:
  - `python manage.py test seed_quiz.tests.test_teacher_flow`
  - 결과: `Ran 54 tests ... OK`
- 추가 표적 검증:
  - `python manage.py test seed_quiz.tests.test_teacher_flow.TeacherFlowTest.test_dashboard_shows_new_tab_navigation_labels`
  - `python manage.py test seed_quiz.tests.test_teacher_flow.TeacherFlowTest.test_bank_select_creates_draft_preview`
  - `python manage.py test seed_quiz.tests.test_teacher_flow.TeacherFlowTest.test_publish_changes_status`
  - 결과: `Ran 3 tests ... OK`

## 실기기 수동 점검 프로토콜 (교사 1명 기준, 10분)
1. PC(가로 1280)에서 대시보드 진입 후 상단 버튼 문구를 확인한다.
- 합격 기준: 새 탭 문구 3종이 보이고 버튼이 한 줄 또는 의도된 2줄로 깨지지 않는다.

2. 방법 A에서 `문제 만들기(바로 저장)` 실행 후 성공 알림을 확인한다.
- 합격 기준: 생성/갱신 개수 알림 후 미리보기로 자동 전환된다.

3. 미리보기에서 `다른 세트 고르기` 클릭.
- 합격 기준: 은행 목록으로 시선이 이동하고 첫 `이 세트 적용` 버튼에 포커스가 간다.

4. 은행 목록에서 `이 세트 적용` 클릭.
- 합격 기준: 버튼에 로딩 표시가 잠깐 보이고 미리보기가 갱신된다.

5. 미리보기에서 `학생에게 배포하기` 클릭.
- 합격 기준: 배포 완료 카드로 전환되고 `학생 대시보드/정답 결과 분석` 버튼이 노출된다.

6. 배포 완료 카드에서 링크 복사/QR 전체화면을 눌러본다.
- 합격 기준: 복사 성공 안내 또는 실패 안내가 즉시 표시되고, QR 모달 열기/닫기가 동작한다.

7. 이미 배포 중 상태에서 새 세트를 다시 배포해 교체 확인창을 띄운다.
- 합격 기준: 취소 시 빈 화면이 아니라 기존 미리보기로 복귀한다.

8. 모바일(가로 360~390)에서 대시보드 재진입 후 같은 흐름 일부(1,3,5)를 반복한다.
- 합격 기준: 버튼 라벨이 잘리지 않고 조작 가능한 높이(약 44px 이상)로 유지된다.

## 남은 리스크(수동 확인 필요)
- 360px급 모바일에서 실제 줄바꿈 체감(문구 길이/폰트 렌더링 차이)은 브라우저 실기기 확인이 필요
- `window.alert` 기반 피드백의 체감은 브라우저/OS별 UX 차이 확인이 필요

## 실기기 결과 기록표 (작성용)
| 항목 | 기기/브라우저 | 결과(PASS/FAIL) | 메모(깨짐/혼란 지점) |
|---|---|---|---|
| 상단 새 탭 버튼 문구/정렬 | PC / Chrome |  |  |
| 저장 성공 후 자동 미리보기 전환 | PC / Chrome |  |  |
| 다른 세트 고르기 후 포커스 이동 | PC / Chrome |  |  |
| 배포 완료 카드 액션 인지 | PC / Chrome |  |  |
| 교체 확인창 취소 복귀 | PC / Chrome |  |  |
| 상단 새 탭 버튼 문구/정렬 | Mobile / Safari |  |  |
| 핵심 버튼 줄바꿈/높이(44px+) | Mobile / Safari |  |  |
| 배포/학생·분석 이동 동선 | Mobile / Safari |  |  |
