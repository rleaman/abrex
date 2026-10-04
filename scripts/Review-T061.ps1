param(
    [switch]$Check,
    [int]$Port = 8765
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot "env313\Scripts\python.exe"
$runner = Join-Path $PSScriptRoot "run_t060_reviewer.py"
$packet = Join-Path $projectRoot "evidence\T060\review-packet-split-v2.json"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "ABREX Python was not found at $python"
}
if (-not (Test-Path -LiteralPath $packet -PathType Leaf)) {
    throw "The corrected T061 packet was not found at $packet"
}

if ($Check) {
    & $python $runner --check
} else {
    & $python $runner --port $Port
}
exit $LASTEXITCODE
