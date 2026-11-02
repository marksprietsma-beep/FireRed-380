# FireRed-380

A Windows-first, locally operated FireRed AI application integrating the Python
readers/API, Node agent, prompts and dashboard from
[GPT Plays Pokemon FireRed](https://github.com/Clad3815/gpt-play-pokemon-firered)
at **9619b101d607ee79b68e1274174ac3b6eeb6ff06**. Personal, non-commercial use;
see [attribution](THIRD_PARTY_NOTICES.md) and [integration/provenance](UPSTREAM_INTEGRATION.md).

Our hardened **0.3.1 Lua bridge and Python transport remain authoritative**.
The app has offline integration coverage. **No live emulator or gameplay pass is
claimed.** The historical v0.2 battery remains 5/8, unchanged. Actual Windows,
ROM/symbol alignment, model capabilities and movement timing await verification.

## Application

- Read-only memory, player/party/PC/bag/save data, text and dialogue decoding.
- Battle/menu/Pokédex/Fly Map recognition, world maps, collision/events/viewport
  and persistent fog-of-war.
- FastAPI on `127.0.0.1:8000`, including `/health`, `/requestData`,
  `/minimapSnapshot`, `/sendCommands`, `/control/pause` and `/control/resume`.
- Node agent and dashboard on `127.0.0.1:9885`, with prompts, memory, objectives,
  progress, summaries, logs, party/inventory/map, action results and token usage.
- Local Ollama by default: `http://127.0.0.1:11434/v1`, model **qwen3.8:27b**.
  No API key or external service is required. Optional OpenAI is explicit.
- No automatic game actions at startup. An operator approves at most ten actions
  per sequence. Each action is bounded and followed by observation/cleanup.

## Install and test on Windows

Tested offline with Python **3.12**, Node **24.19.0**, and an existing Lua interpreter.
Use Node 22+ and Lua 5.3+ (`lua` on PATH or `LUA_BIN` set). No model download is
performed. The scripts use a Python 3.12 virtual environment and lockfiles.

```powershell
.\scripts\Install.ps1
$env:LUA_BIN = 'C:\Tools\Lua\lua.exe' # omit if lua is on PATH
.\scripts\Test.ps1
```

The complete suite includes Python/Lua mocks, API tests, Node provider tests and
mocked local HTTP/WebSocket connectivity. It never requires a real Ollama or mGBA.
The dashboard is static JavaScript; `npm run build` checks server/frontend syntax.
Dependencies and generated runtime state are ignored by Git.

## Choose a testing policy

**Protected mode is the default.** It retains the disposable-save, symmetric
non-overlap, protected-save hash, source/version and OS listener gates documented
in [the hardening runbook](workspace/docs/BRIDGE_HARDENING.md). Without an approved
manifest, emulator access is locked; health and static UI remain available.

**Owner-authorised mode is separately opt-in.** Only the specified Squirrels ROM
and normal adjacent save are allowed:

```text
C:\Emu\1636 - Pokemon Fire Red (U)(Squirrels).gba
C:\Emu\1636 - Pokemon Fire Red (U)(Squirrels).sav
MD5    e26ee0d44e809351c8ce2d73c7400cdd
SHA256 3d0c79f1627022e18765766f6cb5ea067f6b5bf7dca115552189ad65a5c3a8ac
```

Copy `config/owner-authorized.example.json` **outside the checkout**, fill the
reviewed Lua SHA-256, actual mGBA executable/PID and a fresh empty output directory.
After locally verifying the loaded ROM and adjacent save destination, set both
path-confirmation fields true. The owner-mode verifier hashes only that exact ROM
read-only; it does not open the save, second ROM/save, or backups. Save isolation
and preservation are reported **OWNER-WAIVED** (`pass: null`), never passed.
T1–T8 and S3 remain mandatory. No global mGBA setting is changed.

## Local startup sequence

These are instructions for **subsequent local Windows verification**. No emulator
was launched and no game files were accessed during this integration task.

1. Establish the chosen policy before manually launching mGBA 0.10.5. For owner
   mode, verify its current save destination is the authorised adjacent `.sav`;
   do not alter global configuration or access the second ROM or backups. For
   protected mode, establish owner-approved isolation first.
2. Create a fresh empty ASCII-path artifact directory outside the checkout and
   ROM/save directories, without symlinks/junctions. Print the Lua load instructions:

   ```powershell
   .\scripts\Prepare-mGBA.ps1 -OutputDirectory 'C:\FireRed380-test\run-001'
   ```

   Manually enter the printed statements under **Tools → Scripting**. Require
   `READY on 127.0.0.1:8888 v0.3.1`. Keep state commands disabled. Inspect the
   listener PID/executable and update the manifest. This script never launches mGBA.
3. Start the API in a dedicated terminal. Protected mode:

   ```powershell
   .\scripts\Start-API.ps1 -Manifest 'C:\FireRed380-test\protected.json'
   ```

   Or, **only for explicitly authorised adjacent-save modification**:

   ```powershell
   .\scripts\Start-API.ps1 -Manifest 'C:\FireRed380-test\owner.json' -OwnerAuthorizedSaveModification
   ```

   Omitting the manifest starts a locked API suitable for health checks only.
   `Invoke-RestMethod http://127.0.0.1:8000/health` reports mode/authorisation/pause.
4. Start your already-installed Ollama/model manually. Do not assume this model
   exists or supports tools/vision. The application will pause on unsupported or
   malformed responses; it does not silently download or substitute models.
5. In another terminal:

   ```powershell
   .\scripts\Start-Agent.ps1
   .\scripts\Open-Dashboard.ps1
   ```

   The dashboard and agent share port 9885. Click **Refresh observation** to inspect
   authorised read-only state before approving actions. Use **Approve up to 10
   actions** only after reviewing the game state; **Pause / release keys** stops
   the approved sequence. The agent is paused initially and on failures/budget
   exhaustion. No unattended startup or public listener is enabled.
6. Shutdown: click Pause, then run `scripts/Stop.ps1`. Require confirmed Python
   release, close the Node/Python terminals with Ctrl+C, and manually shut down
   the Lua bridge if needed. Do not blindly replay uncertain input requests.

### Standalone live battery (not run here)

Use a fresh output directory/manifest and manually reload the bridge between a
battery run and an application session. Do not run them concurrently. API startup
validates an empty output directory once; observations then create fresh files.

```powershell
# Protected mode
.\.venv\Scripts\python.exe workspace/tests/test_bridge_battery.py --safety-json 'C:\FireRed380-test\protected.json'
# Owner-authorised mode: explicit flag AND manifest opt-in required
.\.venv\Scripts\python.exe workspace/tests/test_bridge_battery.py --safety-json 'C:\FireRed380-test\owner.json' --owner-authorized-save-modification
```

Reports and PNGs go to the approved artifact directory under new UUID names.
Visually compare screenshots with mGBA; offline tests cannot establish this.

### Provider configuration

Copy `server/.env.example` to a **local-only** `server/.env`, or set environment
variables. Configure `AI_PROVIDER`, `AI_BASE_URL`, `AI_MODEL`, `AI_TIMEOUT_MS` and
`AI_VISION` (off by default). Optional OpenAI requires `AI_PROVIDER=openai`, an
explicit endpoint/model and `AI_API_KEY`/`OPENAI_API_KEY` supplied securely.
Local pathfinding never uploads state or executes hosted/generated code.

## Limitations and next verification

See [UPSTREAM_INTEGRATION.md](UPSTREAM_INTEGRATION.md) for all modifications and
exclusions. Short pulses are not yet calibrated to exact one-tile movement. The
local pathfinder conservatively refuses special/unknown terrain, while upstream
terrain observations remain available. Model responses are buffered rather than
streamed token-by-token. Full game-state accuracy, Windows scripts and actual
Ollama model/tool competence still need local validation. The 380-species goal,
trading orchestration and live gameplay completion are not established.

Never commit ROMs, saves, savestates, screenshots, minimaps, credentials or personal
agent histories. `.gitignore` is a commit filter, not runtime save protection.
