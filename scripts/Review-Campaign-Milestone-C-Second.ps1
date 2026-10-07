param(
    [int]$Port = 8766,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot "env313\Scripts\python.exe"
$evidence = Join-Path $projectRoot "evidence\campaign-2026-10\milestone-c"
$packet = Join-Path $evidence "second-review-packet-blind-v1.json"
$state = Join-Path $evidence "second-review-packet-blind-v1.annotations.json"
$lock = Join-Path $evidence "second-review-packet-blind-v1.annotations.lock.json"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python was not found at $python"
}
if (-not (Test-Path -LiteralPath $packet)) {
    throw "Run scripts\prepare_milestone_c_postlock.py before second review"
}

$arguments = @(
    (Join-Path $projectRoot "scripts\run_blind_reviewer.py"),
    $packet,
    "--state", $state,
    "--lock", $lock,
    "--port", $Port
)
if ($NoOpen) {
    $arguments += "--no-open"
}

Push-Location $projectRoot
try {
    & $python @arguments
}
finally {
    Pop-Location
}
