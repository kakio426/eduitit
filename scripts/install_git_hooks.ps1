$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$hooksPath = Join-Path $repoRoot ".githooks"
$preCommitPath = Join-Path $hooksPath "pre-commit"

if (-not (Test-Path $preCommitPath)) {
    Write-Error "pre-commit hook not found: $preCommitPath"
}

git -C $repoRoot config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) {
    throw "failed to set core.hooksPath"
}

Write-Host "[ok] core.hooksPath set to .githooks"
Write-Host "[ok] branch path guard pre-commit hook is active"
