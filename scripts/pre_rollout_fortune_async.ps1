param(
    [switch]$VerboseOutput
)

$ErrorActionPreference = "Stop"

Write-Host "=== Fortune Async Pre-Rollout Check ==="

Write-Host "[1/3] Django system check"
python manage.py check

Write-Host "[2/3] Focused tests"
python manage.py test `
    fortune.tests.test_deepseek_streaming `
    fortune.tests.test_streaming_logic `
    fortune.tests.test_hybrid_api `
    -v 2

Write-Host "[3/3] Verify rollout flags exist in production settings"
$settings = "config/settings_production.py"
$streamFlag = Select-String -Path $settings -Pattern "FORTUNE_ASYNC_STREAM_ENABLED" -SimpleMatch
$apiFlag = Select-String -Path $settings -Pattern "FORTUNE_ASYNC_API_ENABLED" -SimpleMatch

if (-not $streamFlag -or -not $apiFlag) {
    throw "Required rollout flags are missing in $settings"
}

if ($VerboseOutput) {
    Write-Host "--- Flag Lines ---"
    $streamFlag | ForEach-Object { Write-Host $_.Line }
    $apiFlag | ForEach-Object { Write-Host $_.Line }
}

Write-Host "=== Pre-Rollout Check Passed ==="
