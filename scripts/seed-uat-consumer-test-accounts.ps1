[CmdletBinding()]
param(
  [string]$Python,
  [switch]$Json
)

$ErrorActionPreference = 'Stop'

function Get-GitValue {
  param([string[]]$GitArgs)

  $value = (& git @GitArgs 2>$null)
  if ($LASTEXITCODE -ne 0) {
    return 'unknown'
  }
  return (($value | Select-Object -First 1) -as [string]).Trim()
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repoPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (Test-Path $repoPython) {
  $pythonBin = $repoPython
} elseif (-not [string]::IsNullOrWhiteSpace($Python)) {
  $pythonBin = $Python
} else {
  $pythonBin = 'python'
}

$branch = Get-GitValue @('branch', '--show-current')
$head = Get-GitValue @('rev-parse', '--short', 'HEAD')
$seedScript = Join-Path $repoRoot 'scripts\seed_uat_consumer_test_accounts.py'

Write-Host '[uat-seed] Repo path: ' $repoRoot
Write-Host '[uat-seed] Branch:    ' $branch
Write-Host '[uat-seed] HEAD:      ' $head
Write-Host '[uat-seed] Python:    ' $pythonBin
Write-Host '[uat-seed] Accounts:   uat_consumer_test, webuat_consumer'
Write-Host '[uat-seed] Role:       user only'

$guardCode = @'
from src.config import setup_env
from src.auth import is_production_mode
setup_env()
print("production" if is_production_mode() else "non-production")
'@

Push-Location $repoRoot
try {
  $mode = (& $pythonBin -c $guardCode)
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to evaluate runtime environment before seeding."
  }
  $mode = (($mode | Select-Object -First 1) -as [string]).Trim()
  if ($mode -eq 'production') {
    throw 'Refusing to seed UAT consumer accounts in production mode.'
  }

  $args = @($seedScript)
  if ($Json) {
    $args += '--json'
  }
  & $pythonBin @args
} finally {
  Pop-Location
}
