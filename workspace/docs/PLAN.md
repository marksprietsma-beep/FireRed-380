# FireRed-380 — plan

## Phases

- **Phase 0 — audit:** complete. See `REUSE_AUDIT.md`.
- **Phase 1 — Lua bridge:** v0.1–v0.3 source exists. v0.2 was live-tested once and passed 5/8 checks. v0.3 is written but untested. Re-run the full battery on the intended Windows/mGBA setup and require 8/8.
- **Phase 2 — Python controller/API:** not started. Planned local API on port 8000, wrapping the TCP bridge client with validation, health checks, bounded actions and pause/resume.
- **Phase 3 — supervisor/LLM loop:** not started. Observe → reason → one structured action → execute → verify → log. Maximum ten actions per sequence.
- **Phase 4 — supervised gameplay:** not started. Begin with an owner-approved first milestone and verify all state from the game.

## Gates

1. Resolve save isolation before any gameplay or input that could modify game state.
2. Load v0.3 and verify the actual bridge version and loopback binding.
3. Achieve 8/8 on the live bridge battery.
4. Implement and test Phase 2 before connecting the LLM.
5. Keep every game action bounded, observed and auditable.

## Current deliverables

- `STATUS.md`, `RESUME.md`, `CODEX_START_HERE.md`
- `workspace/docs/` architecture, plan, reuse audit, risk log and test protocol
- `workspace/src/` Lua bridge versions and Python TCP client
- `workspace/tests/test_bridge_battery.py`
- `workspace/tools/` Windows menu helpers
