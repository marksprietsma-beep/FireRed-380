param([string]$Manifest, [switch]$OwnerAuthorizedSaveModification)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($Manifest) { $env:FIRERED_TEST_MANIFEST = (Resolve-Path -LiteralPath $Manifest).Path }
else { Remove-Item Env:FIRERED_TEST_MANIFEST -ErrorAction SilentlyContinue }
if ($OwnerAuthorizedSaveModification) {
    if (-not $Manifest) { throw 'Owner mode requires a manifest and explicit opt-in' }
    $env:FIRERED_OWNER_AUTHORIZED_TESTING = '1'
} else { Remove-Item Env:FIRERED_OWNER_AUTHORIZED_TESTING -ErrorAction SilentlyContinue }
$env:FIRERED_ENABLE_RECOVERY_STATES = '0'
& .\.venv\Scripts\python.exe -m uvicorn firered_mgba_bridge:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
