---
name: eduitit-core
description: Eduitit 서비스 개발/수정 작업 시 필수 가드레일과 배포 규칙을 적용한다. 신규 서비스 추가, 템플릿 수정, HTMX/Django 뷰 변경, ensure 커맨드 작성, ServiceManual/ManualSection 구성, 배포 동기화(Procfile/nixpacks/settings_production) 작업에서 사용한다.
---

# Eduitit Core Guardrails

## P0 Rules
- Keep `settings.py` and `settings_production.py` synchronized.
- Never commit `.env`, API keys, or secrets.
- Keep top spacing `pt-32` on pages with fixed navbar.
- Keep Django template tags intact on one line when conditional tags are involved.
- Always provide `ServiceManual` for new services with at least 3 `ManualSection` records.
- Do not overwrite admin-managed fields in `ensure_*` commands (`service_type`, `display_order`, `color_theme`).

## New Service SSOT
- Create a separate Django app for major new services.
- Register URL namespace explicitly.
- Keep template/static scoping:
  - `app/templates/app/...`
  - `app/static/app/...`
- Keep `product.title` string exact across DB, ensure command, and template/view conditions.
- Ensure rich product content:
  - `lead_text`
  - detailed `description`
  - at least 3 `ProductFeature` items.

## Deployment Sync (All 4 Required)
- Update `INSTALLED_APPS`.
- Append `ensure_<app>` in `Procfile` after migrate.
- Mirror same start command in `nixpacks.toml`.
- Register `call_command('ensure_<app>')` in startup tasks.

## Data Rules
- Use migrations (`RunPython`) for DB data changes, not only Django shell edits.
- Keep seed/init logic idempotent (`get_or_create` / `update_or_create`).
- Treat `ensure_*` as existence guarantee, not forced reset.

## Django/HTMX Stability
- Use `select_related` only for required relationships.
- Avoid HTMX polling inside `<template x-if>`.
- Guard JSON parsing from HTML error payloads.
- Enforce CSRF for HTMX POST (global + critical-action double check via `hx-vals`).

## UI Baseline
- Keep base layout section:
  - `pt-32 pb-20 px-4 min-h-screen`
- Maintain Claymorphism style consistency.
- Do not load HTMX/Alpine redundantly in child templates.

## Completion Checklist
- Run `python manage.py check`.
- Re-check template tag fragmentation/line breaks.
- Update `requirements.txt` for new dependencies.
- Validate core flow: create/read/update/delete and download/export if present.

## Manual Visibility Rule
- Publish manual with `is_published=True`.
- List/detail visibility should require:
  - `is_published=True`
  - `product.is_active=True`

## Encoding Safety (Korean Text)
- Treat all template/source files as UTF-8 without BOM.
- Do not use shell pipelines that rewrite files for content edits (for example `Get-Content | Set-Content`) on Korean-heavy files.
- Prefer `apply_patch` for edits; if using scripts/tools, force explicit UTF-8 read/write.
- After editing Korean UI files, run a quick mojibake scan before commit:
  - check for broken tokens like `?`, `�`, `媛`, `�쒕`, `?댁`.
- If corruption is detected, restore from latest clean git revision first, then re-apply logical diffs.
- Keep `.editorconfig` in repo root with UTF-8 defaults and do not remove it.
