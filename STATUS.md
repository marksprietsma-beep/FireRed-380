# FireRed-380 — status

**Last source-state audit:** 2026-11-01, approximately 17:53 CST  
**Repository:** public GitHub repository; source and documentation only  
**Project:** supervised Pokémon FireRed agent

## Task 2 hardening candidate (2026-11-01)

The existing v0.3 file now identifies as **0.3.1**. Reliability fixes and an offline
mock suite are implemented on `codex/bridge-hardening`; **35 Python tests including
18 Lua scenarios pass**, with no failures/errors/skips. No live mGBA test was run.
The historical v0.2 report remains unchanged. Save isolation remains an external
blocker. The historical implementation table below describes the imported checkpoint.

See `workspace/docs/BRIDGE_HARDENING.md` for compatibility changes, pinned 0.10.5 API
evidence, remaining limitations and exact Windows verification instructions.
Phase 2 is not implemented or authorized by this work; await review and approval.

## Current state

| Area | Status | Evidence |
|---|---|---|
| Phase 0 — project/reuse audit | Complete | `workspace/docs/REUSE_AUDIT.md` |
| Lua bridge v0.1 | Historical reference only | Archived under `workspace/archive/legacy/`; do not load |
| Lua bridge v0.2 | Live-tested once | Battery 5/8; T5 failed |
| Lua bridge v0.3 | Written, not live-tested | Contains proposed T5 two-phase release fix and additional commands |
| Python TCP client | Written; T8 fix unverified | `workspace/src/bridge_client.py` |
| Battery test | Written; T7 logging improved | `workspace/tests/test_bridge_battery.py` |
| Last recorded battery | 5/8 | `workspace/state/battery_report.json` (pre-fix v0.2 run) |
| Python API/controller on :8000 | Not started | Planned Phase 2 |
| LLM supervisor | Not started | Planned Phase 3 |
| Supervised gameplay | Not started | Planned Phase 4 |

At the last recorded machine audit, mGBA was not running and ports 8888/8000 were not listening. Ollama 0.40.13 and `qwen3.8:27b` were reported running at that time. Re-check the actual local machine before relying on any runtime state.

## Critical save-integrity issue

The later disk audit found `Pokemon - FireRed Version.sav`, 131,072 bytes, created during the mGBA relaunch window. Its SHA-256 was identical to the three backups of the protected Squirrels save. The writer was not established.

This supersedes the earlier claim that the test ROM had no `.sav` sidecar. **Save isolation is not proven. Do not start gameplay or advance the game until a separate disposable save path is configured and verified.** The original save and backups must remain untouched.

## Bridge battery — last verified run

The 2026-11-01 16:16:21 battery run was against v0.2:

| Test | Result | Detail |
|---|---|---|
| T1 ping/pong | PASS | `pong` |
| T2 frame counter | PASS | Increased between calls |
| T3 memory reads | PASS | 8/16/32-bit and range reads returned values |
| T4 screenshot | PASS | 240×160 PNG |
| T5 timed key press/release | FAIL | A remained pressed after the hold window |
| T6 clear-all interruption | PASS | `clearAll` released active keys |
| T7 connection stability | FAIL | 1 failure in 30 fresh-connection pings |
| T8 multi-command framing | FAIL | Python client type error in `call_raw` |

**The fixes for T5, T7 and T8 are present in the files but have not been verified.** Phase 1 is not complete until the full battery passes 8/8.

## Repository contents

- `workspace/src/FireRedBridgeSocketServer_v0.3.lua` — intended candidate bridge.
- `workspace/src/FireRedBridgeSocketServer_v0.2_fixed.lua` — historical live-tested bridge.
- `workspace/src/bridge_client.py` — TCP client for port 8888.
- `workspace/tests/test_bridge_battery.py` — T1–T8 live battery.
- `workspace/tools/` — Windows menu helpers.
- `workspace/docs/` — architecture, plan, audit, risks and test protocol.
- `instructions/FIRERED_POKEDEX_AGENT_SPEC.md` — full project specification.

ROMs, `.sav` files, backups, `.mgbs` savestates, screenshots and Python bytecode were deliberately excluded from this public repository.

## Next steps

1. Complete the static audit in `CODEX_START_HERE.md`.
2. Resolve and verify save isolation locally before any gameplay or controller input.
3. On the Windows/mGBA setup, load v0.3 and verify the bridge version and loopback listener.
4. Re-run the battery and achieve 8/8. Investigate any failing test from captured evidence.
5. Only then begin Phase 2: the Python controller/API on port 8000.
6. Implement the supervised LLM loop only after the API is tested.

Do not claim success based on code inspection alone.
