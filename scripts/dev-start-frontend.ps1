[CmdletBinding()]
param(
  [string]$BindHost = '127.0.0.1',
  [int]$Port = 5173
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
  param(
    [object[]]$Listeners,
    [string]$ExpectedPath
  )

  foreach ($listener in $Listeners) {
    $ownerProcessId = [int]$listener.OwningProcess
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
    Write-Host "  PID $ownerProcessId ($processName), command references this worktree: $matchesWorktree"
  }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$webRoot = Join-Path $repoRoot 'apps\dsa-web'
$branch = Get-GitValue @('branch', '--show-current')
$head = Get-GitValue @('rev-parse', '--short', 'HEAD')
$frontendUrl = "http://${BindHost}:$Port"

if (-not (Test-Path $webRoot)) {
  throw "Web app directory not found: $webRoot"
}

Write-Host '[dev-frontend] Repo path: ' $repoRoot
Write-Host '[dev-frontend] Branch:    ' $branch
Write-Host '[dev-frontend] HEAD:      ' $head
Write-Host '[dev-frontend] URL:       ' $frontendUrl

$listeners = Get-PortListeners -LocalPort $Port
if ($listeners.Count -gt 0) {
  Write-Warning "Port $Port is already occupied. Stop the existing listener before starting this worktree."
  Write-PortListenerSummary -Listeners $listeners -ExpectedPath $webRoot
  throw "Refusing to start Vite while port $Port is occupied; this prevents reusing a server from another worktree."
}

Push-Location $webRoot
try {
  Write-Host '[dev-frontend] Starting Vite from: ' (Get-Location).Path
  npm run dev -- --host $BindHost --port $Port --strictPort
} finally {
  Pop-Location
}
