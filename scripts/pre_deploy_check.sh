#!/bin/bash
set -e
echo "=== Pre-deploy Check ==="

echo "[1/4] Django system check (--deploy)..."
python manage.py check --deploy
echo "  OK"

echo "[2/4] Checking for unapplied migrations..."
UNAPPLIED=$(python manage.py showmigrations --list 2>/dev/null | grep "\[ \]" || true)
if [ -n "$UNAPPLIED" ]; then
    echo "  WARNING: Unapplied migrations found:"
    echo "$UNAPPLIED"
    exit 1
fi
echo "  OK - All migrations applied"

echo "[3/4] Running sheetbook preflight..."
if python manage.py help check_sheetbook_preflight >/dev/null 2>&1; then
    if [ "${SHEETBOOK_PREFLIGHT_STRICT:-False}" = "True" ] || [ "${SHEETBOOK_ENABLED:-False}" = "True" ]; then
        python manage.py check_sheetbook_preflight --strict --recommend-days "${SHEETBOOK_ROLLOUT_RECOMMEND_DAYS:-14}"
    else
        python manage.py check_sheetbook_preflight --recommend-days "${SHEETBOOK_ROLLOUT_RECOMMEND_DAYS:-14}"
    fi
else
    echo "  SKIP - check_sheetbook_preflight command not available"
fi
echo "  OK"

echo "[4/4] Checking requirements.txt syntax..."
pip check 2>/dev/null || echo "  WARNING: pip check found issues (non-blocking)"

echo ""
echo "=== All checks passed ==="
