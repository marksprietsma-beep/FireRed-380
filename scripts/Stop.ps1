$ErrorActionPreference = 'Stop'
# Ask both layers to pause/release. Never kill the emulator or touch game files.
try { Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:9885/control/pause' | Format-List }
catch { Write-Warning "Node pause unavailable: $_" }
try { $status = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/control/pause'; $status | Format-List }
catch { Write-Warning "Python release could not be confirmed: $_"; throw }
if ($status.authorized) { Write-Host 'Authorised session paused; key release verified.' }
else { Write-Host 'No authorised emulator session existed; no emulator key-state claim is made.' }
Write-Host 'Close Node/Python terminals with Ctrl+C. Shut down the Lua bridge manually if needed.'
