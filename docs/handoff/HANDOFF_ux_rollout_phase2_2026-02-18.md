# Handoff: UX Rollout Phase 2 (2026-02-18)

## Scope

- UX-04 follow-up: finalize `HOME_V2_ENABLED` default and rollback rules.
- UX-05: route fieldization (`Product.launch_route_name`) with legacy-safe fallback.
- UX-06: 768~1024 layout stabilization for V2 home.
- UX-07: initial IA load reduction on V2 home.

## Code Changes

- Added `Product.launch_route_name` field and migration:
  - `products/models.py`
  - `products/migrations/0037_product_launch_route_name.py`
  - `products/admin.py`
- Updated launch URL resolution:
  - `core/views.py`
    - `launch_route_name` is now checked first.
    - legacy title-map remains as fallback for safe transition.
- Removed duplicated title-branch logic from preview modal:
  - `products/views.py` now passes `launch_href`, `launch_is_external`
  - `products/templates/products/partials/preview_modal.html` now uses context values only.
- Adjusted V2 responsive breakpoints and IA load:
  - `core/templates/core/home_v2.html`
  - `core/templates/core/home_authenticated_v2.html`
  - `core/templates/core/includes/purpose_sections.html`
    - SNS sidebar split moved to `xl` breakpoint.
    - purpose section preview is capped (max 2), with `+N more` indicator.
- Finalized rollout default policy in settings:
  - `config/settings.py`
  - `config/settings_production.py`
  - `HOME_V2_ENABLED` default switched to `True` with rollback comment.

## Test Updates

- Updated V1-dependent tests to explicit `HOME_V2_ENABLED=False`:
  - `core/tests/test_home_view.py` (HomeViewTest class)
  - `products/tests/test_views.py` (ProductViewTests class)
- Added route and layout regression coverage:
  - `products/tests/test_launch_routes.py` (new)
  - `products/tests/test_preview.py` (launch target context assertions)
  - `core/tests/test_home_view.py` (launch route precedence, preview-cap behavior, `xl` breakpoint assertions)

## Validation

- Command:
  - `python manage.py test products.tests.test_views products.tests.test_preview products.tests.test_launch_routes core.tests.test_home_view products.tests.test_dashboard_modals core.tests.test_ui_auth -v 1`
- Result:
  - `OK (51 passed)`

## Operational Notes

- Rollout/rollback runbook:
  - `docs/runbooks/HOME_V2_ROLLOUT_RULES.md`
- Legacy title-route map is still active as fallback.
  - Next cleanup step: backfill `launch_route_name` in admin/data migration, then remove fallback map.
