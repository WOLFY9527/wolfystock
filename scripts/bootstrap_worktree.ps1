[CmdletBinding(DefaultParameterSetName = 'Check')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Check')]
    [switch]$Check,
    [Parameter(Mandatory = $true, ParameterSetName = 'Apply')]
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$command = if ($Check) { @('env', 'verify') } else { @('bootstrap', '--ensure') }
& (Join-Path $root 'wolfy.ps1') @command
exit $LASTEXITCODE
