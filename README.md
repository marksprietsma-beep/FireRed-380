# FireRed-380

A Windows-first, supervised Pokémon FireRed agent project. The long-term objective is to register the required 380 National Pokédex species in the primary FireRed save. The project is designed around verified observations, bounded actions, human approval and careful save-file protection.

## Current state

- Phase 0 (project and reuse audit): complete.
- Phase 1 (mGBA Lua bridge): code exists in versions 0.1–0.3. Version 0.2 was live-tested once; the recorded battery result was **5/8**.
- Version 0.3 contains a proposed key-release fix, but it was **written and never loaded or tested**.
- The Python TCP client and test-battery fixes are present but remain unverified.
- The Python controller/API on port 8000, supervisor and gameplay loop have **not** been implemented.
- At the last recorded checkpoint, mGBA was not running and ports 8888/8000 were not listening. Treat this as historical state and re-check locally.

Read `STATUS.md` and `RESUME.md` before making changes. The full design brief is `instructions/FIRERED_POKEDEX_AGENT_SPEC.md`.

## Critical save-safety warning

A later on-disk audit found a `.sav` file beside the ROM used for testing. It was 131,072 bytes and byte-for-byte identical to the three backups of the protected save. The process that created that sidecar was **not established**.

Therefore, the earlier assumption that the test ROM had no save file is withdrawn. **Do not perform gameplay or any action that could advance/save the game until the save path has been isolated and verified.** Do not overwrite, rename, delete or upload any original save or backup as part of this repository work.

## Repository contents and exclusions

This repository is deliberately source-and-documentation only. It does not contain a Pokémon ROM, `.sav` save, `.mgbs` savestate, emulator screenshot or Python bytecode. Those files were present in the supplied archive and were intentionally excluded.

The `.gitignore` blocks common ROM, save, savestate, screenshot, cache and local-secret patterns. Do not weaken those protections to make a test pass.

## Suggested reading order

1. `STATUS.md`
2. `RESUME.md`
3. `CODEX_START_HERE.md`
4. `instructions/FIRERED_POKEDEX_AGENT_SPEC.md`
5. `workspace/docs/ARCHITECTURE.md`, `PLAN.md` and `RISK_LOG.md`
6. `workspace/state/battery_report.json`
7. `workspace/src/FireRedBridgeSocketServer_v0.3.lua`, `bridge_client.py` and `workspace/tests/test_bridge_battery.py`

## Runtime assumptions

The target runtime is Windows with mGBA 0.10.5 and a locally supplied, legally obtained FireRed ROM. The ROM and emulator are not distributed here. The bridge is intended to listen on `127.0.0.1:8888`. The future local controller/API is planned for port 8000; it does not exist yet.

The local model recorded in the checkpoint was Ollama `qwen3.8:27b`. Do not assume Ollama or mGBA is currently running.

## Licensing

No blanket licence is granted for original FireRed-380 material by this repository. See `THIRD_PARTY_NOTICES.md` for attribution and licensing of adapted upstream bridge material.
