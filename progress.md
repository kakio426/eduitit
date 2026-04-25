# 잇티한글 AI 문서 초안 생성 진행 기록

## 작업 기준

- target_app: `doccollab(잇티한글)`
- do_not_touch_apps: `sheetbook`, `hwpxchat/hwpchat`, 무관한 서비스
- 작업 브랜치: `codex/doccollab-ai-draft`, `codex/doccollab-hwpx-output`
- 기준: 최신 `origin/main`
- 결과 목표: AI 요청 → HWPX 초안 생성 → 잇티한글 편집방 바로 열기 → 저장/다운로드

## Plan 1. 제품/구현 계획

### Summary

- `doccollab(잇티한글)`에 "AI에게 요청 → HWPX 초안 생성 → 편집방 바로 열기 → 저장/다운로드" 흐름을 추가한다.
- v1 범위는 교사용 문서 초안: 안내문, 가정통신문, 계획안, 회의록, 보고서, 자유 요청.
- `sheetbook`, `hwpxchat/hwpchat`은 참조, 이관, 수정 대상에서 제외한다.

### Key Changes

- 메인 화면 상단에 `AI 문서` 생성 카드를 추가한다.
- 입력은 `문서 종류` 선택과 `요청 내용` textarea로 제한한다.
- 성공 시 생성된 `room_detail`로 바로 이동한다.
- 새 origin/type으로 `DocRoom.OriginKind.AI_DRAFT`를 추가한다.
- 새 모델 `DocGeneratedDraft`를 추가한다.
- 생성 파이프라인은 학습지 생성 구조와 나란히 둔다.
- `doc_generation_llm.py`: DeepSeek JSON 생성.
- `doc_hwp_builder.py`: 구조화 JSON을 HWPX로 조립.
- `doc_generation_service.py`: quota, LLM, HWPX build, room/revision 생성 orchestration.
- HWPX 생성은 기존 rhwp runtime을 확장한다.
- 새 Node 스크립트 `build_document_hwp.mjs`는 HWPX export로 동작한다.
- v1은 고정 슬롯 템플릿 방식으로 안정성을 우선한다.
- 결과 저장은 `DocRevision.ExportFormat.HWPX_EXPORT`, 파일명은 `{title}.hwpx`로 둔다.

### Interfaces

- URL: `POST doccollab:generate_document`
- 경로: `POST /doc-hub/documents/generate/`
- non-JS는 redirect fallback, JS는 JSON 응답.
- 요청 필드:
  - `document_type`: `notice | home_letter | plan | minutes | report | freeform`
  - `prompt`: 20~2000자
- LLM JSON 스키마:
  - `title`: 80자 이하
  - `subtitle`: 선택
  - `meta_lines`: 문자열 배열, 최대 6개
  - `body_blocks`: `{heading, paragraphs, bullets}` 배열, 최대 8개
  - `closing`: 선택
  - `summary_text`: 160자 이하
- 에러 처리:
  - 빈 요청/초과 길이: 400
  - 일일 한도 초과: 429
  - LLM 실패/HWPX 빌드 실패: 503
  - 예상 가능한 실패는 500 없이 메시지 또는 JSON으로 반환한다.

### Test Plan

- 정상 생성 POST → `DocRoom(origin_kind=AI_DRAFT)` 생성 → `DocGeneratedDraft READY` → `DocRevision HWPX_EXPORT` 생성 → `room_detail` GET 200.
- JSON 생성 요청 성공 응답에 `room_url`, `revision_id`, `download_url`, quota 값 포함.
- 빈 prompt, 초과 prompt, 미지원 document_type, rate limit, LLM 실패, HWPX 빌드 실패 모두 500 없이 처리.
- 생성된 HWPX 다운로드 GET 200 및 `Content-Disposition`에 `.hwpx` 포함.
- 메인 화면에 `AI 문서`, `파일 열기`, `오늘`, `최근`, `공유`가 보이고 설명 문단 과다 없음.
- 변경 JS `node --check`, `npm run build`, `manage.py check`, `makemigrations --check --dry-run`, `doccollab.tests.test_views`.

### Assumptions

- AI provider는 기존 학습지 생성과 동일하게 DeepSeek를 기본값으로 쓴다.
- v1은 완전 자유 조판이 아니라 안정적인 일반 문서 템플릿 조립 방식으로 간다.
- 생성 결과와 편집 저장본은 HWPX로만 남긴다.
- 생성 후 사용자는 바로 rhwp 편집방에서 수정한다.
- 서버 배포 시 새 마이그레이션에 대해 `manage.py migrate --noinput`이 필요하다.

## Plan 2. 직렬/병렬 태스크 분해

### 직렬 태스크

1. 작업 기준선 준비
   - 최신 `origin/main` 기준 `codex/doccollab-ai-draft` 임시 브랜치/워크트리 생성.
   - 변경 범위는 `doccollab`, 필요한 정적 빌드 산출물, `requirements` 정도로 제한.

2. 공통 계약 확정
   - `DocRoom.OriginKind.AI_DRAFT` 추가.
   - `DocGeneratedDraft` 모델/마이그레이션 추가.
   - v1 JSON 스키마 확정: `title`, `subtitle`, `meta_lines`, `body_blocks`, `closing`, `summary_text`.
   - 문서 유형 enum 확정: `notice`, `home_letter`, `plan`, `minutes`, `report`, `freeform`.

3. 통합 서비스 뼈대
   - `create_generated_document_room(user, document_type, prompt)` 서비스 함수 추가.
   - 성공 시 `DocRoom`, `DocRevision(HWPX_EXPORT)`, `DocGeneratedDraft(READY)`를 한 트랜잭션 흐름으로 생성.
   - 실패 시 quota 반환, 상태 기록, 사용자 메시지 규칙 확정.

4. 최종 통합
   - URL/view/form/JS/service/builder를 연결.
   - 생성 성공 후 `room_detail`로 redirect 또는 JSON `room_url` 반환.
   - 생성 문서는 기존 rhwp 편집방에서 바로 열리게 함.

5. 최종 검증/배포
   - `makemigrations --check --dry-run`, `manage.py check`, `doccollab` 테스트.
   - `npm run build`, 변경 JS `node --check`.
   - 생성 POST → 편집방 GET 200 → 다운로드 GET 200 확인.
   - `main` 반영 후 `origin/main` 푸시, 서버에서 `manage.py migrate --noinput`.

### 병렬 태스크

- P1. LLM 생성 모듈
  - `doc_generation_llm.py` 작성.
  - DeepSeek JSON 응답 호출, retry/timeout, JSON 추출, payload normalize.
  - 문서 유형별 프롬프트는 한 파일에서 관리.
  - 빈 제목/본문, 긴 문장, 과도한 항목 수를 normalize 단계에서 제한.

- P2. HWPX 빌더
  - `doc_hwp_builder.py` Python wrapper 작성.
  - `build_document_hwp.mjs` Node/rhwp runtime을 HWPX 출력으로 작성.
  - v1은 범용 문서 템플릿 1개로 시작.
  - page count, file name, output hwpx bytes를 반환.

- P3. UI/UX
  - 메인 화면에 `AI 문서` 카드 추가.
  - `문서 종류` 선택 칩과 `요청 내용` 입력만 전면 배치.
  - 버튼 문구는 `만들기`.
  - 진행/실패 상태는 짧게 표시: `생성 중`, `다시 시도`, `오늘 한도`.

- P4. View/API
  - `POST /doc-hub/documents/generate/` 추가.
  - non-JS는 redirect fallback, JS는 JSON 응답.
  - 예상 가능한 오류는 400/429/503으로 반환하고 raw 500 방지.

- P5. 테스트
  - 모델/마이그레이션 테스트.
  - LLM mock 성공/실패 테스트.
  - HWPX builder mock 성공/실패 테스트.
  - 생성 후 첫 화면 200, 다운로드 200 테스트.
  - 메인 화면 문구/버튼 노출 테스트.

### 의존성

- P1, P2, P3, P4, P5는 공통 계약 확정 이후 병렬 가능.
- P4는 서비스 함수 이름과 응답 shape만 필요하므로 P1/P2 완료 전 mock으로 진행 가능.
- P5는 초반에는 mock 기반으로 병렬 작성하고, 최종 통합 뒤 실제 흐름 테스트를 보강한다.
- 최종 통합은 P1~P4가 끝난 뒤에만 진행한다.

## Progress

- [x] 작업 기준선 준비
- [x] 두 계획을 `progress.md`에 기록
- [x] 공통 계약/모델/마이그레이션 구현
- [x] LLM 생성 모듈 구현
- [x] HWP 빌더 구현
- [x] UI/UX 구현
- [x] View/API 구현
- [x] 테스트 구현
- [x] 통합 검증
- [x] main 반영/푸시
- [x] HWPX 결과물 전환 진행
