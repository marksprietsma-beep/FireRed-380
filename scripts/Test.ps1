$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv\Scripts\python.exe workspace/tests/run_mock_tests.py
if ($LASTEXITCODE -ne 0) { throw 'Python/Lua tests failed' }
& .\.venv\Scripts\python.exe -m compileall -q firered_bridge firered_mgba_bridge.py workspace/src workspace/tests
if ($LASTEXITCODE -ne 0) { throw 'Python syntax checks failed' }
Push-Location server
try {
    npm test
    if ($LASTEXITCODE -ne 0) { throw 'Node tests failed' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Node/frontend checks failed' }
} finally { Pop-Location }
