[CmdletBinding()]
param(
  [string]$BindHost = '127.0.0.1',
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [string]$Python,
  [switch]$RunPreflight,
  [switch]$SeedUatConsumers,
  [switch]$ProbeBackend,
  [switch]$ProbeFrontend,
  [switch]$ProbeCredentials,
  [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

$FORBIDDEN_FIELD_NAMES = @(
  'raw_payload',
  'rawPayload',
  'provider_payload',
  'providerPayload',
  'raw_response',
  'rawResponse',
  'request_body',
  'requestBody',
  'response_body',
  'responseBody',
  'traceback',
  'stackTrace',
  'authorization',
  'bearer',
  'api_key',
  'apiKey',
  'access_token',
  'accessToken',
  'passwordHash',
  'session_id',
  'sessionId',
  'cookie'
)

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
    return $RequestedPython
  }
  return 'python'
}

function Test-ForbiddenFieldName {
  param([string]$Content)

  $lowerContent = $Content.ToLowerInvariant()
  foreach ($fieldName in $FORBIDDEN_FIELD_NAMES) {
    $needle = '"' + $fieldName.ToLowerInvariant() + '"'
    if ($lowerContent.Contains($needle)) {
      return $fieldName
    }
  }
  return $null
}

function Read-ErrorResponseContent {
  param([object]$ErrorRecord)

  try {
    if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
      return [string]$ErrorRecord.ErrorDetails.Message
    }
    $response = $ErrorRecord.Exception.Response
    if ($response -and $response.Content -and $response.Content.ReadAsStringAsync) {
      return [string]$response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    }
    if ($response -and $response.GetResponseStream) {
      $reader = [System.IO.StreamReader]::new($response.GetResponseStream())
      return $reader.ReadToEnd()
    }
  } catch {
    return ''
  }
  return ''
}

function Invoke-BoundedRequest {
  param(
    [string]$BaseUrl,
    [string]$Method,
    [string]$Path,
    [object]$Body = $null,
    [switch]$CheckForbiddenFields,
    [switch]$ExpectInvalidLogin
  )

  $uri = "$BaseUrl$Path"
  $statusCode = 'failed'
  $forbiddenField = $null
  $invalidLogin = $false

  try {
    $requestArgs = @{
      Uri = $uri
      Method = $Method
      UseBasicParsing = $true
      TimeoutSec = 8
    }
    if ($null -ne $Body) {
      $requestArgs.ContentType = 'application/json'
      $requestArgs.Body = ($Body | ConvertTo-Json -Compress)
    }
    $response = Invoke-WebRequest @requestArgs
    $statusCode = [int]$response.StatusCode
    $content = [string]$response.Content
  } catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $statusCode = [int]$_.Exception.Response.StatusCode
      $content = Read-ErrorResponseContent -ErrorRecord $_
    } else {
      $content = ''
    }
  }

  if ($CheckForbiddenFields -and -not [string]::IsNullOrWhiteSpace($content)) {
    $forbiddenField = Test-ForbiddenFieldName -Content $content
  }

  if ($ExpectInvalidLogin -and -not [string]::IsNullOrWhiteSpace($content)) {
    try {
      $json = $content | ConvertFrom-Json
      $invalidLogin = ($json.error -eq 'invalid_login')
    } catch {
      $invalidLogin = $false
    }
  }

  return [PSCustomObject]@{
    Method = $Method
    Path = $Path
    HttpStatus = $statusCode
    ForbiddenField = $forbiddenField
    InvalidLogin = $invalidLogin
  }
}

function Write-ProbeSummary {
  param(
    [string]$Prefix,
    [object]$Result
  )

  if ($Result.ForbiddenField) {
    throw "$Prefix $($Result.Path): forbidden internal field marker detected."
  }
  if ($Result.Path -eq '/api/v1/auth/login' -and -not $Result.InvalidLogin) {
    throw "$Prefix $($Result.Path): expected wrong-password invalid_login response."
  }
  Write-Host "$Prefix $($Result.Path): HTTP $($Result.HttpStatus)"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$branch = Get-GitValue @('-C', $repoRoot, 'branch', '--show-current')
$head = Get-GitValue @('-C', $repoRoot, 'rev-parse', '--short', 'HEAD')
$backendUrl = "http://${BindHost}:$BackendPort"
$frontendUrl = "http://${BindHost}:$FrontendPort"
$pythonBin = Resolve-PythonBin -RepoRoot $repoRoot -RequestedPython $Python
$preflightScript = Join-Path $repoRoot 'scripts\private-beta-preflight.ps1'
$seedScript = Join-Path $repoRoot 'scripts\seed-uat-consumer-test-accounts.ps1'
$results = New-Object System.Collections.Generic.List[object]

Write-Host '[private-beta-smoke] Repo path:   ' $repoRoot
Write-Host '[private-beta-smoke] Branch:      ' $branch
Write-Host '[private-beta-smoke] HEAD:        ' $head
Write-Host '[private-beta-smoke] Backend URL: ' $backendUrl
Write-Host '[private-beta-smoke] Frontend URL:' $frontendUrl
Write-Host '[private-beta-smoke] Default mode: check-only; services, seed, and output files require explicit flags.'
Write-Host '[private-beta-smoke] Browser-level SPA redirect assertions remain Playwright/UAT responsibility.'

if ($RunPreflight) {
  Write-Host '[private-beta-smoke] Preflight: running existing private beta preflight.'
  & $preflightScript -BindHost $BindHost -BackendPort $BackendPort -FrontendPort $FrontendPort -Python $pythonBin
} else {
  Write-Host '[private-beta-smoke] Preflight: skipped; pass -RunPreflight to run scripts\private-beta-preflight.ps1.'
}

if ($SeedUatConsumers) {
  Write-Host '[private-beta-smoke] Seed: running existing UAT consumer seed wrapper.'
  & $seedScript -Python $pythonBin
} else {
  Write-Host '[private-beta-smoke] Seed: skipped; pass -SeedUatConsumers to seed UAT consumer accounts.'
}

$backendListeners = Get-PortListeners -LocalPort $BackendPort
if ($ProbeBackend) {
  if ($backendListeners.Count -eq 0) {
    Write-Host '[private-beta-smoke] Backend probes: skipped; backend port is not listening.'
  } else {
    $backendProbeSpecs = @(
      @{ Method = 'GET'; Path = '/api/health'; CheckForbiddenFields = $false },
      @{ Method = 'GET'; Path = '/api/v1/auth/status'; CheckForbiddenFields = $false },
      @{ Method = 'GET'; Path = '/api/v1/market-overview/macro'; CheckForbiddenFields = $true },
      @{ Method = 'GET'; Path = '/api/v1/market-overview/funds-flow'; CheckForbiddenFields = $true }
    )
    foreach ($spec in $backendProbeSpecs) {
      $result = Invoke-BoundedRequest -BaseUrl $backendUrl -Method $spec.Method -Path $spec.Path -CheckForbiddenFields:([bool]$spec.CheckForbiddenFields)
      Write-ProbeSummary -Prefix '[private-beta-smoke] Backend probe' -Result $result
      $results.Add($result) | Out-Null
    }
    if ($ProbeCredentials) {
      $credentialProbe = Invoke-BoundedRequest `
        -BaseUrl $backendUrl `
        -Method 'POST' `
        -Path '/api/v1/auth/login' `
        -Body @{ username = 'uat_consumer_test'; password = 'not-a-real-password' } `
        -ExpectInvalidLogin
      Write-ProbeSummary -Prefix '[private-beta-smoke] Credential probe' -Result $credentialProbe
      $results.Add($credentialProbe) | Out-Null
    } else {
      Write-Host '[private-beta-smoke] Credential probes: skipped; pass -ProbeCredentials to run wrong-password invalid_login check.'
    }
  }
} else {
  Write-Host '[private-beta-smoke] Backend probes: skipped; pass -ProbeBackend to probe an already-listening backend.'
}

$frontendListeners = Get-PortListeners -LocalPort $FrontendPort
if ($ProbeFrontend) {
  if ($frontendListeners.Count -eq 0) {
    Write-Host '[private-beta-smoke] Frontend probes: skipped; frontend port is not listening.'
  } else {
    foreach ($path in @('/', '/backtest', '/stock/AAPL')) {
      $result = Invoke-BoundedRequest -BaseUrl $frontendUrl -Method 'GET' -Path $path
      Write-ProbeSummary -Prefix '[private-beta-smoke] Frontend probe' -Result $result
      $results.Add($result) | Out-Null
    }
  }
} else {
  Write-Host '[private-beta-smoke] Frontend probes: skipped; pass -ProbeFrontend to probe an already-listening frontend.'
}

if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
  $resolvedOutput = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)
  $outputParent = Split-Path -Parent $resolvedOutput
  if (-not [string]::IsNullOrWhiteSpace($outputParent)) {
    New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
  }
  $results | ConvertTo-Json -Depth 4 | Set-Content -Path $resolvedOutput -Encoding UTF8
  Write-Host '[private-beta-smoke] Output: wrote bounded probe summary to explicit path.'
} else {
  Write-Host '[private-beta-smoke] Output: skipped; pass -OutputPath to write bounded probe summary.'
}
