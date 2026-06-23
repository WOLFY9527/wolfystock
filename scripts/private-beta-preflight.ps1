[CmdletBinding()]
param(
  [string]$BindHost = '127.0.0.1',
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [string]$Python,
  [switch]$Seed,
  [switch]$Probe
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

function Get-ProcessSummary {
  param(
    [object]$Listener,
    [string]$ExpectedPath
  )

  $ownerProcessId = [int]$Listener.OwningProcess
  $processName = 'unknown'
  $matchesWorktree = 'unknown'
  try {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerProcessId" -ErrorAction Stop
    if ($processInfo.Name) {
      $processName = $processInfo.Name
    }
    if ($processInfo.CommandLine) {
      $matchesWorktree = if ($processInfo.CommandLine.IndexOf($ExpectedPath, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
        'yes'
      } else {
        'no'
      }
    }
  } catch {
    $matchesWorktree = 'unknown'
  }

  return [PSCustomObject]@{
    ProcessId = $ownerProcessId
    ProcessName = $processName
    MatchesWorktree = $matchesWorktree
  }
}

function Test-SamePath {
  param(
    [string]$Left,
    [string]$Right
  )

  if ([string]::IsNullOrWhiteSpace($Left) -or [string]::IsNullOrWhiteSpace($Right)) {
    return $false
  }
  return [System.IO.Path]::GetFullPath($Left).TrimEnd('\') -ieq [System.IO.Path]::GetFullPath($Right).TrimEnd('\')
}

function Resolve-PythonBin {
  param(
    [string]$RepoRoot,
    [string]$RequestedPython
  )

  $repoPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
  if (Test-Path $repoPython) {
    return (Resolve-Path $repoPython).Path
  }
  if (-not [string]::IsNullOrWhiteSpace($RequestedPython)) {
    if (Test-Path $RequestedPython) {
      return (Resolve-Path $RequestedPython).Path
    }
    $requestedCommand = Get-Command $RequestedPython -ErrorAction SilentlyContinue
    if ($requestedCommand) {
      return $requestedCommand.Source
    }
    return $RequestedPython
  }
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCommand) {
    return $pythonCommand.Source
  }
  return 'MISSING'
}

function Test-PythonAvailable {
  param([string]$PythonBin)

  if ($PythonBin -eq 'MISSING') {
    return $false
  }
  if (Test-Path $PythonBin) {
    return $true
  }
  return [bool](Get-Command $PythonBin -ErrorAction SilentlyContinue)
}

function Test-ProductionMode {
  param(
    [string]$RepoRoot,
    [string]$PythonBin
  )

$guardCode = @'
import os
from src.config import setup_env
from src.auth import is_production_mode
setup_env()
env_values = [
    str(os.getenv(name, "")).strip().lower()
    for name in ("APP_ENV", "ENVIRONMENT", "DSA_ENV")
]
production_like = any("prod" in value or "production" in value for value in env_values)
if is_production_mode():
    print("production")
elif production_like:
    print("production-like")
else:
    print("non-production")
'@

  Push-Location $RepoRoot
  try {
    $mode = (& $PythonBin -c $guardCode)
    if ($LASTEXITCODE -ne 0) {
      throw "Failed to evaluate runtime environment before seeding."
    }
    return (($mode | Select-Object -First 1) -as [string]).Trim()
  } finally {
    Pop-Location
  }
}

function Invoke-BackendProbe {
  param(
    [string]$BackendUrl
  )

  $paths = @('/api/health/live', '/api/health', '/api/health/ready')
  foreach ($path in $paths) {
    $uri = "$BackendUrl$path"
    try {
      $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 5
      Write-Host "[private-beta-preflight] Probe ${path}: HTTP $($response.StatusCode)"
    } catch {
      $statusCode = 'failed'
      if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $statusCode = [int]$_.Exception.Response.StatusCode
      }
      Write-Warning "[private-beta-preflight] Probe ${path}: $statusCode"
    }
  }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$currentPath = (Get-Location).Path
$currentGitRoot = Get-GitValue @('-C', $currentPath, 'rev-parse', '--show-toplevel')
$branch = Get-GitValue @('-C', $repoRoot, 'branch', '--show-current')
$head = Get-GitValue @('-C', $repoRoot, 'rev-parse', '--short', 'HEAD')
$statusLines = @(& git -C $repoRoot status --short 2>$null)
$cleanStatus = if ($statusLines.Count -eq 0) { 'clean' } else { "dirty ($($statusLines.Count) change(s))" }
$backendUrl = "http://${BindHost}:$BackendPort"
$frontendUrl = "http://${BindHost}:$FrontendPort"
$pythonBin = Resolve-PythonBin -RepoRoot $repoRoot -RequestedPython $Python
$pythonAvailable = Test-PythonAvailable -PythonBin $pythonBin
$backendStartScript = Join-Path $repoRoot 'scripts\dev-start-backend.ps1'
$frontendStartScript = Join-Path $repoRoot 'scripts\dev-start-frontend.ps1'
$seedScript = Join-Path $repoRoot 'scripts\seed-uat-consumer-test-accounts.ps1'
$warnings = New-Object System.Collections.Generic.List[string]

Write-Host '[private-beta-preflight] Repo path:        ' $repoRoot
Write-Host '[private-beta-preflight] Branch:           ' $branch
Write-Host '[private-beta-preflight] HEAD commit:      ' $head
Write-Host '[private-beta-preflight] Worktree status:  ' $cleanStatus
Write-Host '[private-beta-preflight] Backend URL:      ' $backendUrl
Write-Host '[private-beta-preflight] Frontend URL:     ' $frontendUrl
Write-Host '[private-beta-preflight] Python path:      ' $pythonBin
Write-Host '[private-beta-preflight] Backend helper:   ' $backendStartScript
Write-Host '[private-beta-preflight] Frontend helper:  ' $frontendStartScript

if (-not (Test-SamePath -Left $currentGitRoot -Right $repoRoot)) {
  $warnings.Add("Wrong worktree: current git root is '$currentGitRoot', expected '$repoRoot'.") | Out-Null
}

if (-not $pythonAvailable) {
  $warnings.Add("Missing Python/runtime path: '$pythonBin' was not found.") | Out-Null
}

$backendListeners = Get-PortListeners -LocalPort $BackendPort
$frontendListeners = Get-PortListeners -LocalPort $FrontendPort

Write-Host "[private-beta-preflight] Port ${BackendPort} occupied:  $($backendListeners.Count -gt 0)"
foreach ($listener in $backendListeners) {
  $summary = Get-ProcessSummary -Listener $listener -ExpectedPath $repoRoot
  Write-Host "  backend PID $($summary.ProcessId) ($($summary.ProcessName)), command references this worktree: $($summary.MatchesWorktree)"
  if ($summary.MatchesWorktree -eq 'no') {
    $warnings.Add("Backend port $BackendPort is occupied by another process or worktree.") | Out-Null
  }
}

Write-Host "[private-beta-preflight] Port ${FrontendPort} occupied: $($frontendListeners.Count -gt 0)"
foreach ($listener in $frontendListeners) {
  $summary = Get-ProcessSummary -Listener $listener -ExpectedPath $repoRoot
  Write-Host "  frontend PID $($summary.ProcessId) ($($summary.ProcessName)), command references this worktree: $($summary.MatchesWorktree)"
  if ($summary.MatchesWorktree -eq 'no') {
    $warnings.Add("Frontend port $FrontendPort is occupied by another process or worktree.") | Out-Null
  }
}

if ($Probe) {
  if ($backendListeners.Count -eq 0) {
    Write-Host '[private-beta-preflight] Probe: skipped; backend port is not listening.'
  } else {
    Invoke-BackendProbe -BackendUrl $backendUrl
  }
} else {
  Write-Host '[private-beta-preflight] Probe: skipped; pass -Probe to check lightweight backend endpoints.'
}

if ($Seed) {
  if (-not $pythonAvailable) {
    throw "Refusing to seed UAT consumer accounts because Python/runtime path is missing."
  }
  $mode = Test-ProductionMode -RepoRoot $repoRoot -PythonBin $pythonBin
  if ($mode -eq 'production') {
    throw 'Refusing to seed UAT consumer accounts in production mode.'
  }
  if ($mode -eq 'production-like') {
    throw 'Refusing to seed UAT consumer accounts in production-like mode.'
  }
  Write-Host '[private-beta-preflight] Seed: running existing UAT consumer seed wrapper.'
  & $seedScript -Python $pythonBin
} else {
  Write-Host '[private-beta-preflight] Seed: skipped; default check-only mode does not seed.'
}

foreach ($warning in $warnings) {
  Write-Warning "[private-beta-preflight] $warning"
}

if ($warnings.Count -gt 0) {
  Write-Warning "[private-beta-preflight] Review warning(s) before UAT or demo."
}
