$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
Push-Location server
try {
    npm ci --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw 'Node dependency installation failed' }
} finally { Pop-Location }
Write-Host 'Dependencies installed. No emulator, model, or game files were accessed.'
