param(
    [int]$Port = 8765,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot "env313\Scripts\python.exe"
$packet = Join-Path $projectRoot "evidence\T065\review-packet-blind-v1.json"
$state = Join-Path $projectRoot "evidence\T065\review-packet-blind-v1.annotations.json"
$lock = Join-Path $projectRoot "evidence\T065\review-packet-blind-v1.annotations.lock.json"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python was not found at $python"
}
if (-not (Test-Path -LiteralPath $packet)) {
    throw "T065 blind packet was not found at $packet"
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
