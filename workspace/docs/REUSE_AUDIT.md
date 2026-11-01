# Reuse audit

**Audit date:** 2026-11-01  
**Target:** Windows 11, mGBA 0.10.5

## Emulator and ROM observations

- mGBA 0.10.5 was installed on the local Windows machine.
- The local setup contained **two** FireRed ROM files, not three.
- The test session used a second FireRed ROM distinct from the Squirrels-labelled ROM associated with the protected save.
- ROM files are not included in this repository.

## Save-file audit — critical correction

A later on-disk audit found a 131,072-byte file named `Pokemon - FireRed Version.sav` beside the ROM used in the test session. Its modification time was during the mGBA relaunch window on 2026-11-01. Its SHA-256 matched all three backups of the protected Squirrels save byte-for-byte.

The process that created the sidecar was **not established**. Consequently, the earlier assumption that the test ROM had no `.sav` file is false as of that later audit. Do not infer that the test ROM is safe to play. Save isolation must be established and verified before any gameplay.

The three backup files, the sidecar and all other save data are deliberately excluded from this public repository.

## Bridge and runtime

- mGBA 0.10.5 includes the Lua scripting/socket functionality used by the bridge.
- The v0.2 bridge was loaded and live-tested once.
- The battery result was 5/8: T1–T4 and T6 passed; T5, T7 and T8 failed.
- v0.3 was written but not loaded or tested.
- The Python client fix and improved T7 error logging were written but not re-tested.
- At the last recorded audit, mGBA was not running and ports 8888/8000 were not listening.
- Ollama 0.40.13 with `qwen3.8:27b` was reported running at the time of the last audit. Re-check before use.

## Reuse decisions

| Component | Decision | Reason |
|---|---|---|
| mGBA 0.10.5 | Reuse locally | Existing Windows installation; scripting API available |
| ROM | Owner supplies locally | Not distributed by this project |
| Lua bridge | Continue with v0.3 as candidate | v0.2 had a demonstrated key-release bug; v0.3 contains a proposed fix |
| Python client | Retain pending verification | Standard-library TCP client; T8 fix unverified |
| LLM | Local Ollama model as specified by owner | Avoid unnecessary model downloads and remote game control |

## Evidence and limitations

This is a historical machine audit, not a live status endpoint. Re-check the emulator process, socket listener, save paths and model before each run. The project archive included three identical `.sav` backups, a savestate, two screenshots and a Python bytecode cache; those binary/runtime files were excluded from Git.
