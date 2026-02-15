# 운영 진단 실행: 코드 레벨 보완 (4개 항목)

## Context
이전 세션에서 CLAUDE.md에 규칙만 추가하고 실제 코드 적용을 안 한 문제를 해결한다.
문서 인코딩은 검사 결과 문제 없음 (UTF-8 정상) → 스킵.
Tailwind 빌드 전환(#3)은 사용자 요청으로 제외.

---

## 항목 2: A11y 실제 수정 + lint 스크립트

### 2a. missing alt 수정 (3건)
| 파일 | 수정 |
|------|------|
| `artclass/templates/artclass/library.html:133` | `alt=""` 추가 (JS에서 동적 설정되는 모달 이미지) |
| `core/templates/core/partials/post_edit_form.html:18` | `alt="게시물 이미지"` 추가 |
| `core/templates/core/service_guide_detail.html:170` | `alt="{{ section.title }}"` 추가 |

### 2b. outline-none에 포커스 스타일 추가 (13건, 6파일)
모든 해당 요소에 `focus:ring-2 focus:ring-purple-300` 추가:
- `artclass/templates/artclass/setup.html` (1곳)
- `core/templates/core/dashboard_sns.html` (1곳)
- `core/templates/core/partials/post_item.html` (1곳, disabled 제외)
- `core/templates/core/partials/sns_widget.html` (1곳)
- `core/templates/core/partials/sns_widget_mobile.html` (1곳)
- `reservations/templates/reservations/dashboard.html` (8곳)

### 2c. text-gray-400 → text-gray-500 (본문 텍스트, ~25건)
본문/설명 텍스트에 쓰인 `text-gray-400`을 `text-gray-500`으로 일괄 교체.
`text-gray-300`도 `text-gray-500`으로. placeholder/장식은 제외.

### 2d. `check_a11y` 관리 명령어 생성
**새 파일**: `core/management/commands/check_a11y.py` (~80줄)
- `<img` 태그에서 `alt=` 누락 검출 → exit(1)
- `outline-none` 있는데 `focus:` 없는 요소 검출 (경고)
- `text-gray-400`/`text-gray-300` 보고 (정보)

---

## 항목 4: 이미지 최적화 일괄 적용

### `loading="lazy"` 추가 (12건, 8파일)
| 파일 | 라인 |
|------|------|
| `portfolio/templates/portfolio/portfolio_list.html` | 121, 171 |
| `core/templates/core/partials/post_item.html` | 52 |
| `insights/templates/insights/insight_list.html` | 82 |
| `core/templates/core/service_guide_detail.html` | 110, 132, 151, 170 |
| `fortune/templates/fortune/zoo_history.html` | 25 |
| `ssambti/templates/ssambti/history.html` | 25 |
| `artclass/templates/artclass/library.html` | 73 |
| `autoarticle/templates/autoarticle/wizard/step3_draft.html` | 32 |

### `|optimize` 필터 추가 (Cloudinary 이미지, 4파일)
`{% load cloudinary_extras %}` 추가 + `.url` → `.url|optimize`:
- `portfolio/templates/portfolio/portfolio_list.html` (2곳)
- `core/templates/core/partials/post_item.html` (1곳)
- `insights/templates/insights/insight_list.html` (1곳)
- `core/templates/core/service_guide_detail.html` (4곳)

---

## 항목 5: 구조화 로깅 — RequestID 미들웨어

### `core/middleware.py`에 추가 (~30줄)
- `RequestIDMiddleware`: uuid hex 12자리, thread-local 저장, 요청 완료 시 `[REQUEST] rid=... method path status latency_ms` 로그
- `RequestIDFilter`: 모든 로그 레코드에 `request_id` 필드 주입
- static/media 경로는 로깅 제외

### settings.py + settings_production.py LOGGING 업데이트
- `filters` 섹션에 `RequestIDFilter` 등록
- `formatters.verbose.format`에 `[{request_id}]` 추가
- `handlers.console.filters`에 `['request_id']` 추가

### MIDDLEWARE 등록 (양쪽 settings)
- `settings.py`: SecurityMiddleware 바로 다음
- `settings_production.py`: WhiteNoiseMiddleware 바로 다음

---

## 항목 6: Cron 명령어 내구성 보강

### `collect/management/commands/cleanup_collect.py`
line 103~115의 stage 2 루프에서 `req.delete()`를 try/except로 감싸기. 한 건 실패해도 나머지 계속 처리.

### `version_manager/management/commands/delete_expired_versions.py`
1. `@transaction.atomic` 제거
2. `import logging; logger` 추가
3. 루프 내부를 per-item try/except로 감싸기

### `fortune/management/commands/cleanup_old_sessions.py`
1. `import sys, logging` 추가
2. try/except 감싸기, 실패 시 `logger.error()` + `sys.exit(1)`

---

## 실행 순서
1. 항목 6 (Cron) — 가장 작은 범위
2. 항목 5 (RequestID) — 미들웨어 + 양쪽 settings
3. 항목 4 (이미지) — 템플릿 8개
4. 항목 2 (A11y) — 템플릿 다수 + 새 명령어

## 검증
```bash
cd /c/Users/kakio/eduitit && python manage.py check
python manage.py check_a11y  # 0 critical issues
```
