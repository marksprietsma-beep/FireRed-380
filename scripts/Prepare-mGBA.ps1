param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
# Deliberately never launches mGBA or reads any game files. Manual local setup only.
$root = Split-Path $PSScriptRoot -Parent
Write-Host 'After verifying your selected testing policy, manually launch mGBA 0.10.5.'
Write-Host 'Use Tools -> Scripting and enter the following (with an approved empty output directory):'
Write-Output ('FIRERED_BRIDGE_OUTPUT_DIR = "' + $OutputDirectory.Replace('\','/') + '"')
Write-Output 'FIRERED_BRIDGE_ALLOW_STATES = false'
Write-Output ('dofile("' + (Join-Path $root 'workspace/src/FireRedBridgeSocketServer_v0.3.lua').Replace('\','/') + '")')
