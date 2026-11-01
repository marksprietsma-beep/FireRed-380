# Architecture

## Intended supervised loop

```text
Owner / supervisor
       |
       v
LLM planner (local Ollama model)
       |
       v
Future Python supervisor / API (:8000)   [NOT IMPLEMENTED]
       |
       v
Python BridgeClient (TCP client)
       |
       v
mGBA Lua bridge (127.0.0.1:8888)
       |
       v
mGBA + locally supplied FireRed ROM
```

Each supervised step should observe the current screen and structured memory state, request exactly one bounded action, execute it, wait for the game to settle, observe again, verify the outcome and log the evidence. Sequences are capped at ten actions and require human approval.

## Implemented components

1. **mGBA runtime** — target is mGBA 0.10.5 on Windows. The emulator and ROM are local user assets and are not included.
2. **Lua bridge** — `workspace/src/FireRedBridgeSocketServer_v0.3.lua`; intended to run in the mGBA scripting console and listen on `127.0.0.1:8888`. It exposes ping/version/frame, screenshot, read-only memory access, key state, bounded key presses, clear-all, savestate load/save and shutdown commands.
3. **Python TCP client** — `workspace/src/bridge_client.py`; connects to the bridge on port 8888. It is not the planned HTTP API.
4. **Battery test** — `workspace/tests/test_bridge_battery.py`; exercises the bridge and client through T1–T8.
5. **Windows menu helpers** — `workspace/tools/`; attempt to open the mGBA scripting console.

## Planned components

- **Python controller/API on port 8000:** not implemented.
- **Supervisor and LLM loop:** not implemented.
- **Persistent state/objective ledger and trade orchestration:** specified as future work, not implemented.

The checkpoint recorded Ollama `qwen3.8:27b` as the intended local model. Runtime availability must be rechecked.

## Safety invariants

- All emulator-control listeners must bind to `127.0.0.1`, never a LAN/public interface.
- No memory writes or cheats.
- Do not play until the `.sav` isolation issue in `STATUS.md` is resolved.
- Do not upload ROMs, saves, savestates, screenshots or private runtime logs.
- Discrete, bounded inputs; clear keys on interruption.
- Every action must be followed by observation and verification.
- One action per step; no more than ten actions per autonomous sequence.
