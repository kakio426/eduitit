# AGENTS.md

## Branch Separation Policy

- `main` 계열 작업과 `sheetbook` 작업은 반드시 분리한다.
- `sheetbook` 작업은 `feature/sheetbook`에서만 진행한다.
- `main` 반영 목적 작업은 `hotfix/main-ops`에서만 진행한다.
- `main` 계열 작업 중에는 `feature/sheetbook` 파일/브랜치를 건드리지 않는다.
- `sheetbook` 작업 중에는 `main`/`hotfix/main-ops` 파일을 건드리지 않는다.

## Triggered Workflow (Korean Shortcut)

- 사용자가 아래처럼 요청하면 동일 규칙을 고정 적용한다.
  - `hotfix/main-ops로 진행해서 main에 올려줘`
  - `sheetbook랑 분리해서 hotfix/main-ops에서 작업하고 main 반영까지 해줘`
- 위 요청을 받으면 항상 아래 순서로 진행한다.
  1. `hotfix/main-ops`에서 작업
  2. `sheetbook` 작업과 완전 분리
  3. 테스트 후 `main` 반영(merge)까지 처리
  4. 별도 지시가 없으면 `origin/main` 푸시까지 수행
- 사용자가 `커밋만`이라고 말하면 merge/push 없이 커밋에서 멈춘다.

## Service Integration Guardrails

- 작업 시작 전에 반드시 `target_app`과 `do_not_touch_apps`를 먼저 선언한다.
- 요청 범위가 `global`이 아니면 공용 파일(`base.html`, 공용 CSS/JS, settings)은 수정하지 않는다.
- 시각 변경보다 동작 보존을 우선한다: 라우팅, 모달 닫기(배경/ESC), 포커스 복귀, 핵심 버튼 동작.
- 한글 깨짐 징후가 보이면 기능 수정보다 텍스트/인코딩 복구를 먼저 처리한다.
- `fetch` 기반 액션은 `response.ok` 검증과 실패 피드백(alert/toast)을 반드시 포함한다. 빈 `catch`는 금지한다.
- 폼 변경 시 required 모델 필드를 숨기면 안 된다. 숨길 경우 optional/default 처리 후 `form.errors`를 반드시 노출한다.
- JS 확인 UX(모달/2단계)에는 non-JS 제출 폴백을 유지해 "버튼 무반응" 상태를 만들지 않는다.
- 신규 서비스는 독립 앱 + URL namespace를 기본으로 한다.
- 신규 서비스 등록 시 `ensure_<app>`에서 `Product`와 함께 `ServiceManual(is_published=True)` 및 `ManualSection` 3개 이상을 동시에 생성한다.
- 머지 전 최소 검증:
  - `python manage.py check`
  - 변경 JS에 대한 `node --check`
  - 핵심 화면 런타임 스모크(주요 탭/버튼 1회) + 브라우저 콘솔 `ReferenceError` 0건
- 작업트리가 더러우면 요청 범위 파일만 선택 커밋하고, 커밋 전 `git diff --cached`를 확인한다.
