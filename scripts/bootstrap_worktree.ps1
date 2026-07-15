[CmdletBinding(DefaultParameterSetName = 'Check')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Check')]
    [switch]$Check,
    [Parameter(Mandatory = $true, ParameterSetName = 'Apply')]
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$mode = if ($Check) { '--check' } else { '--apply' }
& python (Join-Path $PSScriptRoot 'worktree_preflight.py') bootstrap $mode
exit $LASTEXITCODE
