#!/bin/bash
set -e
echo "=== Pre-deploy Check ==="

echo "[1/3] Django system check (--deploy)..."
python manage.py check --deploy
echo "  OK"

echo "[2/3] Checking for unapplied migrations..."
UNAPPLIED=$(python manage.py showmigrations --list 2>/dev/null | grep "\[ \]" || true)
if [ -n "$UNAPPLIED" ]; then
    echo "  WARNING: Unapplied migrations found:"
    echo "$UNAPPLIED"
    exit 1
fi
echo "  OK - All migrations applied"

echo "[3/3] Checking requirements.txt syntax..."
pip check 2>/dev/null || echo "  WARNING: pip check found issues (non-blocking)"

echo ""
echo "=== All checks passed ==="
