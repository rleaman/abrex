param(
    [switch]$Check,
    [int]$Port = 8765
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot "env313\Scripts\python.exe"
$runner = Join-Path $PSScriptRoot "run_t057_reviewer.py"

if ($Check) {
    & $python $runner --check
} else {
    & $python $runner --port $Port
}
exit $LASTEXITCODE
