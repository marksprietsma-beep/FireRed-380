# Codex hand-off

This file is the starting brief for a new Codex session.

## First task: audit, do not immediately implement

Read `README.md`, `STATUS.md`, `RESUME.md`, `instructions/FIRERED_POKEDEX_AGENT_SPEC.md`, all files in `workspace/docs/`, the battery report, and the bridge/client/test source.

Produce a concise audit covering:

1. What is implemented, what has actually been tested, and what remains unverified.
2. Whether v0.3's key-release logic and the Python client's `call_raw` fix are correct by inspection.
3. Any protocol mismatch between the Lua bridge, Python client and battery test.
4. Any security, save-integrity or reliability risks.
5. The smallest safe next steps, in order.

Do not claim that v0.3 works: it has never been loaded or live-tested. The only recorded live battery result is 5/8 against v0.2.

## Hard constraints

- **Do not run gameplay or send controller inputs** until the save-file isolation problem in `STATUS.md` is resolved and verified.
- Do not overwrite, rename, delete, upload or modify any ROM, `.sav`, backup or savestate.
- Do not download ROMs or game assets.
- Do not add ROMs, saves, savestates, screenshots, personal logs, credentials or machine-specific files to Git.
- Keep all control listeners bound to `127.0.0.1`; never expose emulator control to a LAN or public interface.
- Windows first. Do not introduce Linux, WSL, Docker or platform-specific validation unless an indispensable blocker is documented and the owner agrees.
- Preserve the ≤10-actions-per-sequence limit, one action per observation, human approval for irreversible actions, and honest reporting.
- Do not implement Phase 2 until the bridge battery passes 8/8 on the intended Windows/mGBA setup.
- Do not assume that the omitted `pre_v03_reload.mgbs` savestate is available. It was deliberately not published.

## Immediate static checks

Static checks that do not launch the emulator or modify game data may be run:

```powershell
python -m py_compile .\workspace\src\bridge_client.py .\workspace\tests\test_bridge_battery.py
```

The live battery test requires a locally running mGBA instance with the bridge loaded. It is not a cloud-only test.

## After the audit

Wait for owner direction before making behavioural changes. If authorised to proceed, prepare a minimal, reviewable patch and explain exactly what it changes. Do not treat a passing static check as a passing live bridge test.
