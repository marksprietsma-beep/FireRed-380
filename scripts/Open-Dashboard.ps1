$ErrorActionPreference = 'Stop'
Invoke-RestMethod -Uri 'http://127.0.0.1:9885/health' | Format-List
Start-Process 'http://127.0.0.1:9885'
