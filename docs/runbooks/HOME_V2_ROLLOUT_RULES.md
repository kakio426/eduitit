# HOME V2 Rollout Rules

Last Updated: 2026-02-18
Owner: Web + Ops

## Default Policy

- `HOME_V2_ENABLED` default is `True` in both `config/settings.py` and `config/settings_production.py`.
- V2 is treated as the baseline home experience unless explicitly disabled via environment variable.

## Rollback Policy

- Emergency rollback: set `HOME_V2_ENABLED=False` and redeploy.
- Partial rollback for search only: set `GLOBAL_SEARCH_ENABLED=False`.
- Tablet policy rollback: set `ALLOW_TABLET_ACCESS=False` if tablet layout issues are found.

## Release Checklist

1. Confirm env flags:
   - `HOME_V2_ENABLED`
   - `GLOBAL_SEARCH_ENABLED`
   - `ALLOW_TABLET_ACCESS`
2. Apply DB migrations:
   - `python manage.py migrate`
3. Verify launch targets are configured:
   - `python manage.py shell -c "from products.models import Product; print(Product.objects.filter(external_url='', launch_route_name='').count())"`
   - If count > 0, confirm each product intentionally lands on detail page.
4. Run smoke checks:
   - anonymous home
   - authenticated home
   - product preview modal launch button
   - tablet width (768~1024)
5. Run targeted tests before release:
   - `python manage.py test products.tests.test_views products.tests.test_preview products.tests.test_launch_routes core.tests.test_home_view products.tests.test_dashboard_modals core.tests.test_ui_auth -v 1`

## Fast Incident Decision Tree

1. Home-wide V2 issue: flip `HOME_V2_ENABLED=False`.
2. Search-only issue: flip `GLOBAL_SEARCH_ENABLED=False`.
3. Tablet-specific issue: flip `ALLOW_TABLET_ACCESS=False` and keep V2 enabled.

## UX-05~07 Dependencies

- Legacy title-route fallback has been removed from runtime resolver.
- Route backfill is handled by migration `products/migrations/0038_backfill_launch_route_names.py`.
- New internal-launch products must set `launch_route_name` (or `external_url`) at creation time.
- 768~1024 layout behavior now relies on `xl` breakpoint for SNS sidebar split.
- Purpose sections intentionally show a capped preview list for reduced first-screen cognitive load.
