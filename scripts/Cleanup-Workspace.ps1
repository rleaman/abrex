<#!
.SYNOPSIS
    Audits and optionally removes generated local workspace artifacts.

.DESCRIPTION
    This script is intentionally conservative for OneDrive-backed repositories.
    Without -DeleteSafe it performs an audit only. With -DeleteSafe it removes
    only items classified as SafeToDelete, and records every success and failure
    in a JSON report. Repository data, environments, source files, and tracked
    files are protected by default.

.EXAMPLE
    .\scripts\Cleanup-Workspace.ps1

.EXAMPLE
    .\scripts\Cleanup-Workspace.ps1 -DeleteSafe

.EXAMPLE
    .\scripts\Cleanup-Workspace.ps1 -DeleteSafe -ReportPath .\cleanup-report.json
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter()]
    [string] $Root = (Get-Location).Path,

    [Parameter()]
    [switch] $DeleteSafe,

    [Parameter()]
    [string] $ReportPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
$reportName = if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    "cleanup-report-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss')
} else {
    $ReportPath
}
$reportInput = if ([IO.Path]::IsPathRooted($reportName)) { $reportName } else { Join-Path $resolvedRoot $reportName }
$resolvedReport = [IO.Path]::GetFullPath($reportInput)

function Get-RelativePath([string] $Path) {
    return $Path.Substring($resolvedRoot.Length).TrimStart('\', '/')
}

function Test-Tracked([string] $Path) {
    $relative = Get-RelativePath $Path
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $null = & git -C $resolvedRoot ls-files --error-unmatch -- $relative 2>$null
    $ErrorActionPreference = $oldErrorActionPreference
    return ($LASTEXITCODE -eq 0)
}

function Add-Candidate([IO.FileSystemInfo] $Item, [string] $Category, [string] $Reason) {
    $fullPath = $Item.FullName
    $tracked = Test-Tracked $fullPath
    $classification = if ($tracked) { 'ProtectedTracked' } else { $Category }
    $candidates.Add([ordered]@{
            Path           = $fullPath
            RelativePath   = Get-RelativePath $fullPath
            Type           = if ($Item.PSIsContainer) { 'Directory' } else { 'File' }
            Classification = $classification
            Reason         = $Reason
            ExistsAtAudit  = $true
            Attributes     = [string]$Item.Attributes
            LengthBytes    = if ($Item.PSIsContainer) { $null } else { $Item.Length }
            LastWriteTime  = $Item.LastWriteTime.ToString('o')
            Action         = 'NotAttempted'
            Error          = $null
        }) | Out-Null
}

$candidates = [Collections.Generic.List[object]]::new()

# Safe artifacts are exact, well-known outputs of local development tools.
@('.mypy_cache', '.pytest_cache', '.ruff_cache', '.tox', '.nox', 'htmlcov') |
    ForEach-Object {
        $item = Get-Item -LiteralPath (Join-Path $resolvedRoot $_) -Force -ErrorAction SilentlyContinue
        if ($null -ne $item) { Add-Candidate $item 'SafeToDelete' 'Tool cache or local test/coverage output.' }
    }

Get-ChildItem -LiteralPath $resolvedRoot -Force -ErrorAction Stop |
    Where-Object { $_.Name -match '^\.pytest-' -or $_.Name -match '^pytest-(cache-files|of-)' } |
    ForEach-Object { Add-Candidate $_ 'SafeToDelete' 'Temporary pytest workspace at repository root.' }

Get-ChildItem -LiteralPath $resolvedRoot -Force -File -ErrorAction Stop |
    Where-Object { $_.Name -match '^\.coverage(?:\..+)?$' } |
    ForEach-Object { Add-Candidate $_ 'SafeToDelete' 'Local coverage database.' }

# Do not recurse through data/, environments, .git/, or other large protected
# trees. These are reported below as a whole and are never scanned for caches.
foreach ($scanRootName in @('src', 'tests', 'scripts')) {
    $scanRoot = Join-Path $resolvedRoot $scanRootName
    if (-not (Test-Path -LiteralPath $scanRoot -PathType Container)) { continue }
    Get-ChildItem -LiteralPath $scanRoot -Force -Recurse -Directory -ErrorAction Stop |
        Where-Object { $_.Name -eq '__pycache__' } |
        ForEach-Object { Add-Candidate $_ 'SafeToDelete' 'Python bytecode cache.' }

    Get-ChildItem -LiteralPath $scanRoot -Force -Recurse -File -ErrorAction Stop |
        Where-Object { $_.Extension -in @('.pyc', '.pyo') } |
        ForEach-Object { Add-Candidate $_ 'SafeToDelete' 'Python bytecode file.' }
}

# These are useful to identify but require an explicit human decision.
foreach ($name in @('data', 'env313', '.venv', 'venv', 'env')) {
    $item = Get-Item -LiteralPath (Join-Path $resolvedRoot $name) -Force -ErrorAction SilentlyContinue
    if ($null -ne $item) { Add-Candidate $item 'ReviewBeforeDelete' 'Project data or Python environment; may be expensive or irreplaceable.' }
}

$deleted = 0
$failed = 0
# Remove children before their containing cache directory so a mixed cache
# (or a stray .pyc) produces accurate results rather than misleading lock/
# "path not found" failures for items already removed in the same run.
foreach ($candidate in ($candidates | Sort-Object { $_.Path.Length } -Descending)) {
    if ($candidate.Classification -ne 'SafeToDelete') {
        $candidate.Action = 'ProtectedOrReview'
        continue
    }

    if (-not $DeleteSafe) {
        $candidate.Action = 'WouldDelete'
        continue
    }

    try {
        if ($PSCmdlet.ShouldProcess($candidate.Path, 'Remove generated artifact')) {
            Remove-Item -LiteralPath $candidate.Path -Recurse -Force -ErrorAction Stop
            $candidate.Action = 'Deleted'
            $deleted++
        } else {
            $candidate.Action = 'ShouldProcessDeclined'
        }
    } catch {
        $candidate.Action = 'DeleteFailed'
        $candidate.Error = [ordered]@{
            Message       = $_.Exception.Message
            Type          = $_.Exception.GetType().FullName
            HResult       = $_.Exception.HResult
            NativeError   = if ($_.Exception.PSObject.Properties.Name -contains 'NativeErrorCode') { $_.Exception.NativeErrorCode } else { $null }
            Recommendation = 'Close Python, pytest, editors, and sync clients; retry. If it persists, inspect OneDrive status and the path/attributes.'
        }
        $failed++
        Write-Warning ("Could not remove {0}: {1}" -f $candidate.RelativePath, $_.Exception.Message)
    }
}

$report = [ordered]@{
    GeneratedAt       = (Get-Date).ToString('o')
    Root               = $resolvedRoot
    Mode               = if ($DeleteSafe) { 'DeleteSafe' } else { 'AuditOnly' }
    SafeItemsFound     = @($candidates | Where-Object Classification -eq 'SafeToDelete').Count
    ReviewItemsFound   = @($candidates | Where-Object Classification -eq 'ReviewBeforeDelete').Count
    ProtectedItemsFound = @($candidates | Where-Object Classification -eq 'ProtectedTracked').Count
    Deleted            = $deleted
    DeleteFailures     = $failed
    Items              = $candidates
}

$reportDirectory = Split-Path -Parent $resolvedReport
if (-not (Test-Path -LiteralPath $reportDirectory)) {
    New-Item -ItemType Directory -Path $reportDirectory -Force -WhatIf:$false | Out-Null
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resolvedReport -Encoding utf8 -WhatIf:$false

Write-Output ("Cleanup audit complete: {0} safe, {1} review, {2} protected; {3} deleted, {4} failed." -f `
        $report.SafeItemsFound, $report.ReviewItemsFound, $report.ProtectedItemsFound, $deleted, $failed)
Write-Output ("Report: {0}" -f $resolvedReport)
if (-not $DeleteSafe) { Write-Output 'Audit only. Re-run with -DeleteSafe to remove SafeToDelete items.' }
if ($failed -gt 0) { exit 2 }
