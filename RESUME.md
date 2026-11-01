# FireRed-380 — resume / recovery notes

This file is the operational hand-off. Start with `README.md` and `STATUS.md`; use `CODEX_START_HERE.md` for the first Codex task.

## One-paragraph state

The project audit is complete. The mGBA Lua bridge has three generations: v0.2 was live-tested and passed 5/8 checks; v0.3 contains the proposed timed-key release fix but was never loaded or tested. The Python client and test changes for T8/T7 are also unverified. The API/controller on port 8000 and the LLM supervisor do not exist yet. At the last machine audit, mGBA was closed and ports 8888/8000 were down. Most importantly, a `.sav` sidecar appeared beside the test ROM and was byte-identical to the protected save backups. Do not play or advance the game until save isolation is proven.

## Files to read

- `STATUS.md` — authoritative current project state.
- `instructions/FIRERED_POKEDEX_AGENT_SPEC.md` — full goals and constraints.
- `workspace/src/FireRedBridgeSocketServer_v0.3.lua` — intended bridge version.
- `workspace/src/FireRedBridgeSocketServer_v0.2_fixed.lua` — version that produced the 5/8 live test.
- `workspace/src/bridge_client.py` — Python TCP client.
- `workspace/tests/test_bridge_battery.py` — live bridge test battery.
- `workspace/state/battery_report.json` — historical pre-fix results.
- `workspace/docs/` — architecture, plan, reuse audit, risk log and test protocol.
- `workspace/tools/` — Windows helpers for opening the mGBA scripting menu.

## Local runtime recovery — only after save isolation is addressed

The ROM, emulator, saves and savestate are not stored in this repository. Do not assume any previous absolute Windows path remains valid.

1. Identify the intended local mGBA 0.10.5 installation and the user's legally obtained FireRed ROM.
2. Before launching or interacting with the game, establish exactly which `.sav` path mGBA will use. The prior test-ROM sidecar matched the protected save backups; do not overwrite or reuse it. Obtain owner approval for the isolation method.
3. Launch mGBA normally and verify the process/window.
4. Open **Tools → Scripting**. The included `workspace/tools/mgba_menu_cmd.ps1` attempts to invoke the native menu item; inspect its output and verify the console actually opened. A GUI fallback is documented in the historical notes.
5. In the mGBA scripting console, load the v0.3 bridge using its actual local path, for example:

   ```lua
   dofile("C:/path/to/FireRed-380/workspace/src/FireRedBridgeSocketServer_v0.3.lua")
   ```

6. Verify that the console reports v0.3 and that the server listens on `127.0.0.1:8888`.
7. Run the battery:

   ```powershell
   python .\workspace\tests\test_bridge_battery.py
   ```

8. Require **8/8 PASS** before implementing Phase 2.

The `pre_v03_reload.mgbs` savestate was intentionally not included in this public repository. Do not attempt to restore it unless the owner supplies the local file and confirms it is the intended checkpoint.

## Known historical failure modes

- `python3` was not on the original machine's PATH; `python` was.
- PowerShell `Start-Process` failed silently in the earlier session; `cmd /c start` worked then. Re-check rather than assuming.
- mGBA's scripting menu was not exposed through the automation UI. The Win32 menu helper was written, but end-to-end success was not confirmed.
- The emulator exited during the previous session; cause unknown.
- v0.3 has not been loaded. Do not infer that it works.
- The original save backups are not in Git and must stay outside the repository.

## Standing constraints

- Windows first; no WSL, Docker or Linux validation unless the owner approves a documented need.
- Preserve game saves. No ROM or save downloads.
- One action per observation; maximum ten actions per autonomous sequence.
- Human approval for irreversible actions.
- Verify actual results and report uncertainty honestly.
