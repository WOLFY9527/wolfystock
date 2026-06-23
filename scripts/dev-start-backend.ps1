[CmdletBinding()]
param(
  [string]$BindHost = '127.0.0.1',
  [int]$Port = 8000,
  [string]$Python,
  [switch]$PrintCommand,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ExtraArgs
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

function Get-PortListeners {
  param([int]$LocalPort)

  try {
    return @(Get-NetTCPConnection -State Listen -LocalPort $LocalPort -ErrorAction Stop)
  } catch {
    return @()
  }
}

function Write-PortListenerSummary {
  param([object[]]$Listeners)

  foreach ($listener in $Listeners) {
    $ownerProcessId = [int]$listener.OwningProcess
    $processName = 'unknown'
    try {
      $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerProcessId" -ErrorAction Stop
      if ($processInfo.Name) {
        $processName = $processInfo.Name
      }
    } catch {
      $processName = 'unknown'
    }
    Write-Host "  PID $ownerProcessId ($processName)"
  }
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
$backendUrl = "http://${BindHost}:$Port"
$mainPath = Join-Path $repoRoot 'main.py'
$command = @($mainPath, '--serve-only', '--host', $BindHost, '--port', "$Port")
if ($ExtraArgs.Count -gt 0) {
  $command += $ExtraArgs
}

Write-Host '[dev-backend] Repo path: ' $repoRoot
Write-Host '[dev-backend] Branch:    ' $branch
Write-Host '[dev-backend] HEAD:      ' $head
Write-Host '[dev-backend] URL:       ' $backendUrl
Write-Host '[dev-backend] Python:    ' $pythonBin
Write-Host '[dev-backend] Env:        main.py loads repo .env via src.config.setup_env()'

if ($PrintCommand) {
  Write-Host '[dev-backend] Command:   ' "$pythonBin $($command -join ' ')"
  exit 0
}

$listeners = Get-PortListeners -LocalPort $Port
if ($listeners.Count -gt 0) {
  Write-Warning "Port $Port is already occupied. Stop the existing backend or choose another -Port."
  Write-PortListenerSummary -Listeners $listeners
  throw "Refusing to start backend while port $Port is occupied."
}

Push-Location $repoRoot
try {
  & $pythonBin @command
} finally {
  Pop-Location
}
