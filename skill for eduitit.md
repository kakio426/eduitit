# Eduitit Skill (Compressed)

이 문서는 `CLAUDE.md` + `SERVICE_INTEGRATION_STANDARD.md`의 핵심만 압축한 실행 규칙이다.
목표는 토큰 절약 + 재발 버그 방지다.

## 1) P0 금지/필수
- `settings.py` 변경 시 `settings_production.py` 반드시 동기화.
- `.env`, API 키, 시크릿 커밋 금지.
- 모든 페이지 상단 여백 `pt-32` 유지 (고정 Nav 가림 방지).
- Django 템플릿 태그 분절 금지:
  - `{% ... %}`, `{{ ... }}` 내부/앞뒤 줄바꿈으로 깨뜨리지 말 것.
  - 특히 `{% if ... %}`는 한 줄 유지.
- 신규 서비스에 `ServiceManual` 누락 금지.
  - 최소 `ManualSection` 3개 이상.
- `ensure_*` 커맨드에서 Admin 관리 필드 강제 덮어쓰기 금지.
  - 예: `service_type`, `display_order`, `color_theme`.

## 2) 신규 서비스 추가 SSOT
- 대형 기능은 독립 Django app으로 분리 (`models/views/urls`).
- URL namespace 필수:
  - `path('app/', include('app.urls', namespace='app'))`
- 템플릿/정적 경로 강제:
  - `app/templates/app/...`
  - `app/static/app/...`
- 제목 SSOT:
  - `product.title` 조건문/분기 문자열은 DB/ensure 타이틀과 100% 일치.
- Product 풍성도:
  - `lead_text`, `description`, `ProductFeature >= 3`.

## 3) 배포 파이프라인 필수 4곳
`ensure_<app>` 추가 시 아래 4곳 동시 반영:
1. `INSTALLED_APPS`
2. `Procfile` (`migrate` 뒤 `ensure_*`)
3. `nixpacks.toml` (`Procfile`과 동일 명령 순서)
4. `run_startup_tasks()`의 `call_command('ensure_*')`

하나라도 빠지면 대시보드 미노출/502/환경 불일치 발생 가능.

## 4) 데이터 규칙
- DB 데이터 변경은 shell 수동 수정으로 끝내지 말고 `RunPython` 마이그레이션으로 반영.
- 초기/보장 데이터 로직은 멱등성 유지:
  - `get_or_create` / `update_or_create` 우선.
- 배포마다 실행되는 `ensure_*`는 “존재 보장” 중심으로 작성.

## 5) Django/HTMX 안정성 규칙
- `select_related`는 필수 FK만.
  - 선택적 관계(예: `author__userprofile`)는 무리하게 `select_related` 금지.
- `<template x-if>` 안에 HTMX polling/요청 요소 배치 금지.
  - 필요 시 `x-show` + 바깥 HTMX 요소로 유지.
- JSON 파싱 전 HTML 응답 여부 방어.
  - `Unexpected token '<'` 대응.
- HTMX POST는 CSRF 보장:
  - 전역 헤더 주입 + 중요 액션은 `hx-vals`로 이중 검증.

## 6) UI/UX 기준
- 베이스 레이아웃:
  - `<section class="pt-32 pb-20 px-4 min-h-screen">`
- Claymorphism 스타일 유지.
- 라이브러리 중복 로드 금지:
  - HTMX/Alpine는 `base.html` 기준 1회.

## 7) 구현 전/후 체크
구현 전:
- 간단한 Implementation Plan 먼저 제시.

구현 후:
- `python manage.py check`
- 템플릿 태그 분절/줄바꿈 파손 재검토
- 신규 라이브러리 `requirements.txt` 반영
- 수동 테스트 핵심 동선(생성/조회/수정/삭제 + 다운로드)

## 8) 서비스 매뉴얼 최소 기준
- `ServiceManual.is_published`로 노출 제어.
- 목록/상세 조회 조건:
  - `is_published=True` + `product.is_active=True`
- 매뉴얼 없는 활성 서비스는 준비중으로 명확히 분리.


## 9) Mobile Board Fit Rule (Game Services)
- Scope: all grid-board games (isolation, breakthrough, chess-like variants).
- Never ship hardcoded JS grid width like `repeat(cols, 52px)` for mobile gameplay.
- Use viewport-aware CSS clamp for cell size and set only metadata from JS (`--cols`, `--cell-max`).
- Container safety defaults:
  - `overflow-x: hidden|clip`
  - `overscroll-behavior-x: none`
  - `touch-action: pan-y`
- QA required before merge:
  - 320/360/390 width checks
  - no horizontal page slide during play
  - no clipped side columns
  - verify at least isolation + breakthrough (+ new variant)
