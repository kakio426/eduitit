# 전체 서비스 UX 감사 진행표

## 감사 원칙

- 한 번에 한 서비스 묶음만 분석/수정한다.
- 교사의 기존 성공 흐름은 유지하고, 실패/막힘/무반응 경험만 고친다.
- 모바일 `390x844`와 데스크톱 `1440x900`을 함께 확인한다.
- 상단바 침범, 중복 상단바, 가로 넘침, `ReferenceError`, 무반응 버튼을 완료 전 반드시 확인한다.
- `sheetbook`은 retired service로 제외한다.

## 현재 완료 상태

| 순서 | 서비스 | 라우트 | 분석 대상 | 상태 | 발견 이슈 | 수정 여부 | 검증 |
|---:|---|---|---|---|---|---|---|
| 1 | 홈/core | `/` | 첫 화면, 인증 브리지, 즐겨찾기, AI 교무비서, 오늘 일정 | 완료 | 홈 달력/AI 교무비서 피드백 혼선 | 완료 | main 반영 완료 |
| 2 | classcalendar/calendar | `/classcalendar/center/` | 목록, 상세, 생성, 공유, 모바일 편집 제한 | 완료 | 모바일 편집/상태 피드백 혼선 | 완료 | main 반영 완료 |
| 3 | noticegen | `/noticegen/` | 알림장 생성, 수정, 복사 | 완료 | 전체화면 로딩, 입력 근처 오류 부재, 동의/서명 연결 혼선 | 완료 | main 반영 완료 |
| 4 | timetable | `/timetable/` | 시간표 생성, 공유 편집, 자동저장 | 완료 | JSON 실패, alert/prompt/confirm, 만료 링크 404 | 완료 | main 반영 완료 |
| 5 | reservations | `/reservations/entry/` | 특별실 예약, 충돌, 권한, 모바일 | 완료 | 실패 시 alert/raw 오류, 날짜 제한 혼선 | 완료 | main 반영 완료 |
| 6 | schoolcomm/messagebox/quickdrop/parentcomm | `/schoolcomm/`, `/messagebox/`, `/quickdrop/`, `/parentcomm/` | 교사 커뮤니케이션 묶음 | 완료 | 전송/삭제/웹소켓 실패 피드백 혼선 | 완료 | main 반영 완료 |
| 7 | collect/consent/signatures/docsign | `/collect/`, `/consent/`, `/signatures/`, `/docsign/` | 수합, 동의, 서명, 문서 확인 | 완료 | 다운로드/서명/파일 실패 복구 약함 | 완료 | main 반영 완료 |
| 8 | doccollab/hwpxchat/ocrdesk/pdfhub/slidesmith/docviewer | `/doc-hub/`, `/hwpx-chat/`, `/ocrdesk/`, `/pdf/`, `/slidesmith/`, `/docviewer/` | 문서 작업 묶음 | 완료 | alert, 전체화면 로딩, JSON 실패, 잘못된 파일 피드백 | 완료 | 103 tests OK, 모바일/데스크톱 스모크 OK |

## 남은 진행 순서

| 순서 | 서비스 | 라우트 | 분석 대상 | 상태 | 발견 이슈 | 수정 여부 | 검증 |
|---:|---|---|---|---|---|---|---|
| 9 | textbooks/textbook_ai/edu_materials/edu_materials_next/schoolprograms/infoboard | `/textbooks/`, `/textbook-ai/`, `/edu-materials/`, `/edu-materials-next/`, `/schoolprograms/`, `/infoboard/` | 수업 자료 묶음 | 다음 진행 | 미분석 | 미정 | 대기 |
| 10 | autoarticle/encyclopedia/guide_recorder/version_manager/handoff/qrgen | `/autoarticle/`, `/encyclopedia/`, `/guide-recorder/`, `/version-manager/`, `/handoff/`, `/qrgen/` | 보조 업무 도구 | 대기 | 미분석 | 미정 | 대기 |
| 11 | happy_seed/seed_quiz/ssambti/studentmbti/artclass/blockclass | `/happy-seed/`, `/seed-quiz/`, `/ssambti/`, `/studentmbti/`, `/artclass/`, `/blockclass/` | 학급 활동 도구 | 대기 | 미분석 | 미정 | 대기 |
| 12 | chess/janggi/fairy_games/reflex_game/colorbeat/math_games/mancala/ppobgi/fortune | `/chess/`, `/janggi/`, `/fairy-games/`, `/reflex-game/`, `/colorbeat/`, `/math-games/`, `/mancala/`, `/ppobgi/`, `/fortune/` | 활동/게임/기타 도구 | 대기 | 미분석 | 미정 | 대기 |
| 13 | products/portfolio/accounts/insights/manuals | `/products/`, `/portfolio/`, `/accounts/`, `/insights/`, `/manuals/` | 탐색, 계정, 매뉴얼, 운영성 화면 | 대기 | 미분석 | 미정 | 대기 |

## 다음 실행 기준

- 사용자가 `다음 진행해줘`라고 하면 9번 `수업 자료 묶음`부터 진행한다.
- 분석 후 바로 임의 수정하지 않고, 교사 성공 흐름 보존 여부와 막힘 위험을 먼저 검증한다.
- 수정이 필요하면 해당 서비스 묶음만 건드리고, 공용 레이아웃/모델/마이그레이션은 별도 승인 전까지 제외한다.
