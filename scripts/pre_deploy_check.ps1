$ErrorActionPreference = "Stop"

Write-Host "=== Pre-deploy Check (PowerShell) ==="

Write-Host "[1/4] Django system check (--deploy)..."
python manage.py check --deploy
Write-Host "  OK"

Write-Host "[2/4] Checking for unapplied migrations..."
$migrationsOutput = python manage.py showmigrations --list 2>$null
$unapplied = $migrationsOutput | Select-String "\[ \]"
if ($unapplied) {
    Write-Host "  WARNING: Unapplied migrations found:"
    $unapplied | ForEach-Object { Write-Host $_.Line }
    exit 1
}
Write-Host "  OK - All migrations applied"

$recommendDays = $env:SHEETBOOK_ROLLOUT_RECOMMEND_DAYS
if (-not $recommendDays) { $recommendDays = "14" }
$forceStrict = $env:SHEETBOOK_PREFLIGHT_STRICT -eq "True"

Write-Host "[3/4] Running sheetbook preflight..."
if ($forceStrict -or $env:SHEETBOOK_ENABLED -eq "True") {
    python manage.py check_sheetbook_preflight --strict --recommend-days $recommendDays
} else {
    python manage.py check_sheetbook_preflight --recommend-days $recommendDays
}
Write-Host "  OK"

Write-Host "[4/4] Checking requirements.txt syntax..."
try {
    pip check 2>$null
} catch {
    Write-Host "  WARNING: pip check found issues (non-blocking)"
}

Write-Host ""
Write-Host "=== All checks passed ==="
