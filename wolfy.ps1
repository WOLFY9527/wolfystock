[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$WolfyArgs
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = $env:WOLFYSTOCK_BOOTSTRAP_PYTHON
$pythonArgs = @()
$isolationArgs = @('-E', '-s', '-B')
if (-not $python) {
    $python = (Get-Command python3.11 -ErrorAction SilentlyContinue).Source
}
if (-not $python) {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $python = $pyLauncher.Source
        $pythonArgs = @('-3.11')
    }
}
if (-not $python) {
    Write-Error '{"status":"error","reasonCode":"supported_bootstrap_python_missing","message":"CPython 3.11 is required; set WOLFYSTOCK_BOOTSTRAP_PYTHON explicitly."}'
    exit 1
}
$valid = & $python @pythonArgs @isolationArgs -c 'import platform,sys; raise SystemExit(0 if platform.python_implementation() == "CPython" and sys.version_info[:2] == (3, 11) else 1)'
if ($LASTEXITCODE -ne 0) {
    Write-Error '{"status":"error","reasonCode":"unsupported_bootstrap_python","message":"Bootstrap interpreter must be CPython 3.11."}'
    exit 1
}
$entrypoint = Join-Path $root 'scripts/wolfy.py'
& $python @pythonArgs @isolationArgs $entrypoint @WolfyArgs
exit $LASTEXITCODE
