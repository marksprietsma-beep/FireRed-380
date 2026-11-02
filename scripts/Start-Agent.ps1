param([ValidateSet('ollama','openai')][string]$Provider = 'ollama', [string]$Model, [string]$Endpoint)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) 'server')
$env:AI_PROVIDER = $Provider
if ($Model) { $env:AI_MODEL = $Model }
if ($Endpoint) { $env:AI_BASE_URL = $Endpoint }
Write-Host 'Starting local dashboard/agent, paused. No action sequence is automatically approved.'
npm start
exit $LASTEXITCODE
