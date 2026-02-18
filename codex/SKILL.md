---
name: eduitit-core
description: Core guardrails for Eduitit service development and maintenance, including Django/HTMX changes, ensure command safety, ServiceManual setup, and deployment sync rules.
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
- When using title-based launch routing in templates (for example `products/templates/products/partials/preview_modal.html`), always add an explicit branch for the new service.
- Ensure rich product content:
  - `lead_text`
  - detailed `description`
  - at least 3 `ProductFeature` items.

## Launch Routing Guardrail
- For internal services, set `external_url=''` and map the launch URL explicitly to Django route.
- After adding a new product, validate click flow from dashboard modal:
  - expected: service route opens
  - failure pattern: redirects to `home` due to missing title branch.
- First triage for "service click goes home":
  - check `product.title` exact match (SSOT)
  - check launch URL branch in `products/templates/products/partials/preview_modal.html`.

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
- On ModelForm pages, do not omit required fields from templates unless they are explicitly optional/defaulted server-side.
- Always render validation errors on failed POST (`form.errors`, `non_field_errors`) so silent failures are impossible.

## UI Baseline
- Keep base layout section:
  - `pt-32 pb-20 px-4 min-h-screen`
- Maintain visual consistency with the existing page/app design system.
- Do not force Claymorphism on services that already use a different established UI language.
- For game/interactive services, prioritize readability, tap-target size, and state clarity over decorative consistency.
- Do not load HTMX/Alpine redundantly in child templates.

## Mobile Board Fit Rule (Game Services)
- Scope: all grid-board games (for example `isolation`, `breakthrough`, chess-like variants).
- Do not ship hardcoded JS grid width like `repeat(cols, 52px)` for gameplay UIs.
- Use viewport-aware CSS clamp sizing for board cells and set only metadata from JS (`--cols`, `--cell-max`).
- JS grid template pattern:
  - `gridTemplateColumns: repeat(cols, minmax(0, var(--cell-size)))`
- Prevent unintended horizontal page movement on mobile:
  - `overflow-x: hidden|clip`
  - `overscroll-behavior-x: none`
  - `touch-action: pan-y`
- Required QA gate before merge:
  - validate widths `320`, `360`, `390`
  - no horizontal page slide during play
  - no clipped side columns
  - verify at least `isolation` and `breakthrough` (plus new variant if added)

## UI Change Control
- For broad UI changes, define scope first: `global`, `app-level`, or `single-page`.
- If scope is not global, do not modify shared base styles/components beyond the target scope.
- When updating UI, keep behavior parity first (routing, modal close, keyboard actions), then visual polish.
- Record in commit/notes:
  - changed surface area
  - intentional visual differences
  - unaffected services/pages verified

## Action Confirmation Reliability
- Confirmation modal/step UX is allowed, but critical actions must still resolve to a normal server submit.
- Provide non-JS fallback for critical submits (`noscript` button or direct submit path).
- Required QA for critical buttons on mobile:
  - tap leads to visible state change (modal or submit)
  - confirm actually persists data
  - invalid input shows user-facing errors

## Canonical Priority
- If older guidance conflicts, follow these first:
  - preserve stable service UI unless explicit redesign is requested
  - limit UI edits to declared scope
  - restore Korean text integrity before additional feature/style edits

## Document Sync Protocol
- Keep these three documents aligned on the same change date:
  - `claude.md`
  - `SERVICE_INTEGRATION_STANDARD.md`
  - `codex/SKILL.md`
- For platform-level policy updates, add a short canonical section near the top before legacy bodies.
- Do not delete legacy sections without user approval; mark new rules as higher-priority canonical guidance.
- When content is partially corrupted, add a clean canonical block first so operators can continue safely before full text restoration.

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

## Enterprise Delivery Pack (Add-on Workflow)

Use this add-on workflow when requests involve enterprise hardening, async rollout, or service reliability upgrades.

### Trigger Hints
- "enterprise-grade", "production hardening", "async migration", "rollout", "stability", "SLO", "smoke check"

### Required Execution Order
1. Baseline scan
- Confirm current deploy/runtime shape (`Procfile`, `nixpacks.toml`, settings parity).
- Confirm queue backend assumptions (default: DB queue).

2. Risk hardening
- Remove raw exception leaks from user/API/health responses.
- Ensure timeout/retry/circuit-breaker around external AI/API dependencies.

3. Behavior validation
- Align health/integration tests with real routing and auth behavior.
- Verify critical endpoints for 200/302 expectations based on product policy.

4. Deployment validation
- Run `python manage.py check`.
- Run relevant service health tests.
- Run pre/post deploy smoke checks for critical flows.

### DB Queue-Specific Rules
- Assume DB queue as default backend; avoid Redis-only design assumptions.
- Every queued job must define retry budget, terminal failure state, and operator recovery path.
- Keep job payload minimal and deterministic; reference primary keys rather than large serialized objects.

### Output Contract
When applying this workflow, report:
- what was hardened
- what was validated
- what remains as operational risk

## Incident Addendum: Korean Encoding Corruption (2026-02-17)
- Symptoms:
  - Korean UI text became mojibake (`?`, broken glyph clusters) in edited blocks.
  - Mixed forms appeared in one file (normal UTF-8 + escaped unicode + corrupted text).
- Root Causes:
  - Terminal display encoding mismatch (especially on Windows shell) hid true file state.
  - Wide text rewrite patterns increased accidental re-encoding/BOM insertion risk.
  - Functional edits were applied before full text normalization.
- Recovery Sequence (mandatory):
  1. Pause feature edits.
  2. Normalize file encoding first (UTF-8, no BOM).
  3. Restore user-facing Korean strings from known-good text.
  4. Re-apply functional diffs.
  5. Validate with syntax/runtime checks.
- Prevention:
  - Avoid broad regex rewrites on Korean-heavy templates/scripts.
  - Prefer targeted line patches.
  - Keep one canonical representation for Korean text per file.
