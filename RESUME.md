# Resume / operational hand-off

Read `README.md`, `STATUS.md`, `UPSTREAM_INTEGRATION.md` and
`THIRD_PARTY_NOTICES.md` first. The current branch is `codex/bridge-hardening`;
PR #1 must remain a draft and must not be merged without owner direction.

The owner explicitly authorised the pinned full application integration after the
bridge audit/hardening tasks. The API/agent/dashboard now exist; older statements
that they were unimplemented describe the imported historical checkpoint.

## What to preserve

- Hardened Lua/Python 0.3.1 is authoritative; never start the upstream Lua bridge
  or a second emulator-control listener. No arbitrary memory-write/cheat API.
- Protected mode is default, including symmetric directory-separation and
  protected-file hash checks. No manifest means emulator access stays locked.
- Owner mode is an explicit exception only for the exact Squirrels ROM/save pair
  in `config/owner-authorized.example.json`. It hashes the ROM read-only, permits
  the normal adjacent save and records S1/S2 as OWNER-WAIVED, not passed.
- No backup copying, deletion, generation or pruning. No access to the second
  ROM/save. No global mGBA configuration changes in owner mode.
- Agent starts paused; approve at most ten actions; observe after each action.
  Failures/uncertain replies require operator review, not automatic action replay.
- Do not commit runtime histories, maps, screenshots, game files or credentials.

## Repeatable development

Windows: `scripts/Install.ps1`, then `scripts/Test.ps1` (Python 3.12, Node 22+,
Lua 5.3+). Cloud: `.venv/bin/python workspace/tests/run_mock_tests.py`, then
`npm --prefix server test` and `npm --prefix server run build`. ASGI/local HTTP
fixtures may need the executor's local-socket permission; no real model or emulator
is required. Python compileall covers the package/API/client/tests.

## Subsequent local verification

Follow the exact README startup sequence. `Prepare-mGBA.ps1` prints manual Lua
loading commands and never launches the emulator. Fill a new local safety manifest,
verify the actual ROM/save destinations, bridge hash and listener PID/executable.
Use a fresh artifact directory for every battery run/application session.

Start API and Node in separate terminals, then open the dashboard. Refresh a
read-only observation before approving a bounded sequence. To stop, pause through
the UI and run `scripts/Stop.ps1`; require confirmed key release before closing
services. The default provider is local Ollama, model qwen3.8:27b; no model download
or paid key is assumed. Unsupported tools/vision must fail visibly.

No live emulator test was performed in this integration task. Historical v0.2
battery remains 5/8. Current offline mocks validate code contracts only, not ROM
alignment, real movement, physical save destinations or game progress. Keep those
uncertainties explicit in subsequent work.
