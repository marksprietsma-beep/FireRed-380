# CHANGELOG

Chronological. Newest first. Every meaningful action is recorded here.

## 2026-11-01 — archive review and GitHub publication

- Inspected the supplied `FireRed-380.7z` archive. It contained the source, specifications, project notes, tests and runtime evidence; no ROM was present.
- Published source and documentation only. Excluded three `.sav` backups, the `.mgbs` savestate, two PNG screenshots and Python bytecode. None of those files were uploaded.
- Re-hashed the three archived save backups: all three were byte-for-byte identical. The separate on-disk audit also found a `.sav` sidecar beside the test ROM with the same hash. Its writer is unknown. This supersedes the earlier “test ROM has no `.sav`” safety assumption.
- Updated `STATUS.md`, `RESUME.md`, `DECISIONS.md`, `REUSE_AUDIT.md`, `RISK_LOG.md`, `ARCHITECTURE.md`, `PLAN.md` and `TEST_PROTOCOL.md` to reflect the corrected save risk and current verified state.
- Added a public-repository `.gitignore` for ROMs, saves, savestates, screenshots, caches and local secrets.
- Added attribution for the adapted Lua bridge material. Upstream project: `https://github.com/Clad3815/gpt-play-pokemon-firered`; licence: CC BY-NC 4.0.
- The v0.3 bridge, Python client fix and battery fixes remain unverified. No live emulator test was performed during this repository import.

## 2026-11-01 (later — bridge live-tested, T5/T7/T8 diagnosed, v0.3 written, mGBA cycled)
**Phase 1 bridge first live test + fixes (all three fixes still UNVERIFIED as of 17:42):**
- **Wrote + ran the test battery** `workspace\tests\test_bridge_battery.py` (8 tests). **v0.2** (`FireRedBridgeSocketServer_v0.2_fixed.lua`) was loaded into the running mGBA (PID 7280) via the scripting console `dofile` — **first successful live bridge session** (port 8888 verified LISTENING on that PID).
- **Battery result 16:16:21** (`workspace\state\battery_report.json`): **5/8 PASS (T1–T4, T6)**.
  - ✅ T1 ping/pong (`reply='pong'`) · T2 frame counter 330105→330128 (Δ23) · T3 memory reads (read8(0x0)=0x2, read16(0x03007000)=0xc8a1, range_hex[128]) · T4 screenshot 240×160 `t4_baseline.png` (vision-verified FireRed screen) · T6 keys clear after clearAll mid-hold (0x0000).
  - ❌ **T5** discrete A press: `during=0x0001` but `after-window=0x0001` (key stuck). **Root cause (verified in Lua):** v0.2 `step_presses` removed the press entry on the `addKeys` frame, so the `clearKeys` release branch was unreachable.
  - ❌ **T7** stability: 30 fresh-connection pings, **1 failure** (wall 1.34 s, avg 45 ms); no error captured — unexplained, possibly transient.
  - ❌ **T8** multi-command framing: `expected a bytes-like object, str found` → **client-side** bug in `bridge_client.py` (~line 87, `b"".join` over str fragments).
- **Savestate insurance:** `workspace\state\pre_v03_reload.mgbs` (21,070 B) captured 16:57 via live `bridge.saveStateFile` (mid-intro position) before cycling mGBA.
- **Fixes written (NOT yet re-tested):**
  - `workspace\src\FireRedBridgeSocketServer_v0.3.lua` (373 lines / 12,741 B) — **two-phase key holding**: `added` flag separates the add-frame from the release-frame (`clearKeys` at expiry, entry dropped next frame); adds `bridge.version`="0.3", `bridge.loadStateFile`, `bridge.shutdown`. Syntax-checked (node `luaparse`).
  - `workspace\src\bridge_client.py` — T8 fix: join str fragments then encode once (was `b"".join` over strs).
  - `workspace\tests\test_bridge_battery.py` — T7 now records `last_err` for each failing ping.
- **mGBA cycled to load v0.3:** `taskkill /F /PID 7280` → freed 8888 → **PowerShell `Start-Process mGBA.exe` failed silently (exit 1, no window)** → relaunched via `cmd /c start "" "local mGBA installation" "local FireRed ROM (not included)"` → new **PID 30664**, title screen reached (screenshot verified: "mGBA - Pokemon - FireRed Version (USA, Europe) (Rev 1) - 0.10.5").
- **Console-open attempts (end-to-end still UNCONFIRMED):** computer_use UIA click on Tools menu failed (mGBA window not UIA-visible); `key "alt"` rejected by the computer_use parser; SendKeys Alt+T (`mgba_tools_menu.ps1`) ran "TOOLS_MENU_OPENED" unconfirmed; discovered mGBA's menu is a Qt **native Win32 HWND** (not in UIA) → wrote Win32 `GetMenu`/`GetSubMenu`/`GetMenuItemID`/`SendMessage` scripts and executed `mgba_menu_send.ps1`. Scripts preserved to `workspace\tools\mgba_menu_send.ps1` and `mgba_menu_cmd.ps1` (PostMessage variant).
- **mGBA exited later in the session** (gone from `tasklist` by 17:21; no crash dumps found; cause **unverified** — last recorded action was the native-menu probe). Ports 8888/8000 **not listening** (verified 17:21). Ollama 0.40.13 verified running at 11434.
- **Checkpoint (this) written 17:42** at user request `/summarize "Pokemon"`; STATUS.md / RESUME.md updated to current verified state; "Pokemon" row added to `project-index.md`.

## 2026-11-01
- **Checkpoint created (pause):** at user request — established STATUS.md, RESUME.md, CHANGELOG.md, DECISIONS.md. Implementation paused before the live mGBA test.
- **Phase 0 delivered:** wrote STATUS.md, workspace\docs\{PLAN,REUSE_AUDIT,ARCHITECTURE,TEST_PROTOCOL,RISK_LOG}.md.
- **Bridge hardened:** fixed a Lua local-shadowing bug — `accept_connection`, `on_received`, `dispatch` are now plain assignments to their forward-declared locals (not `local function`, which creates a shadowing second local and leaves the forward-declared one nil, breaking cross-closures).
- **Bridge syntax-verified:** node `luaparse` (Lua 5.3) parses the 276-line bridge clean, 26 top-level statements.
- **Bridge written:** `workspace\src\FireRedBridgeSocketServer.lua` — minimal self-contained mGBA Lua socket server (port 8888). Commands: ping, frame, screenshot, read8/16/32, readRangeHex, keys, holdKeys (multi-key, discrete press/release), saveStateFile, clearAll. Patches applied during first pass: (a) removed a dangling `pcallSafe` forward-reference in the logger, (b) added forward declarations, (c) hardened `parse_addr` (0x / decimal / bare-hex) and `to_bitmask` (case-insensitive multi-key), (d) upgraded `holdKeys` to multi-key + frames.
- **Reference cloned (proven socket API):** `clad.lua` + `pokemongym` to `%LOCALAPPDATA%\Temp\fr_probe`. Confirmed via mGBA `CHANGES.txt` that socket scripting is native to this 0.10.5 build (no fork needed).
- **Save protected:** 3× backed up the on-disk save to `workspace\backups\` — `20261101-144344`, `last-known-good.sav`, `PokemonFireRed_US_primary_20261101-143557.sav` (each 131072 B). All three and the live save share sha256 `b5a41c37…02260` → verified byte-identical.
- **Phase 0 audit (0.1–0.5):**
  - Emulator = mGBA 0.10.5, running, loaded ROM `local FireRed ROM (not included)` (no `.sav` on disk → safe).
  - ROMs found (not downloaded): `1636 - Pokemon Fire Red (U)(Squirrels).gba` (+ a second and a third FireRed copy) in `C:/Emu`.
  - Prior bridge = **none on this laptop** (no lua/py bridge, no :8888/:8000 listeners). Previous implementation was not transferred.
  - Ollama 0.40.13 + `qwen3.8:27b` live on 11434 (vision+tools+thinking, GPU).
  - Toolchain: Python 3.14.9, node 26.12, git 2.53.
  - Reuse/rebuild decided: keep mGBA instance + ROM + LLM; rebuild bridge + Python client.
  - Test protocol + risk register written (`TEST_PROTOCOL.md`, `RISK_LOG.md`).
- **Setup:** created `FireRed-380\{workspace\{docs,src,tests,state,logs,backups,third_party}}`; moved the spec into `FireRed-380\instructions\`.

## (prior context, condensed)
- User defined the FireRed-380 spec (Phases 0–4) and the strict safety policy.
- Qwen 9B was the prior failure mode (unreliable inputs, stuck at intro); user switched the trial to `qwen3.8:27b`.
