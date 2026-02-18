# Handoff: UX Rollout Phase 3 (2026-02-18)

## Scope Completed

1. `UX-05` follow-up:
   - `launch_route_name` data backfill migration added.
   - legacy title-based runtime route fallback removed.
2. Ops follow-up:
   - deploy/rollback checklist updated with migration + launch-target verification steps.

## Code/Doc Changes

- Route resolver cleanup:
  - `core/views.py`
    - `_resolve_product_launch_url` now resolves by:
      - `external_url` -> direct
      - `launch_route_name` -> reverse
      - fallback -> `product_detail`
    - title-map fallback removed.
- Data migration:
  - `products/migrations/0038_backfill_launch_route_names.py`
    - backfills known products (e.g. 쌤BTI, 간편 수합, 교사 백과사전, 학교 예약 시스템, 윷놀이, DutyTicker 등).
- Remaining title-branch cleanup:
  - `products/templates/products/list.html`
    - special-case condition now checks `launch_route_name` instead of `title`.
- Runbook update:
  - `docs/runbooks/HOME_V2_ROLLOUT_RULES.md`
    - added `migrate` and launch-target validation commands.
    - updated dependency section to reflect title-map fallback removal.

## Tests

- Added regression assertion for no title-based fallback:
  - `products/tests/test_launch_routes.py`
    - `test_resolver_no_longer_uses_title_based_fallback`

## Validation

- Command:
  - `python manage.py test products.tests.test_views products.tests.test_preview products.tests.test_launch_routes core.tests.test_home_view products.tests.test_dashboard_modals core.tests.test_ui_auth -v 1`
- Result:
  - `OK (52 passed)`
