# FireRed-380 — current status

**2026-11-01: full upstream integration candidate, awaiting review and Windows verification.**

| Area | Implemented / evidence |
| --- | --- |
| Source | Upstream 9619b101d607ee79b68e1274174ac3b6eeb6ff06 imported with licence, original-file hashes and modification/provenance report |
| Transport | Existing hardened 0.3.1 Lua/Python layer remains the only emulator transport; upstream adapter uses it exclusively |
| Python | Memory/symbols, state, player/party/PC/bag/save, text, UI, map/collision/events/viewport and FastAPI connected |
| Node/dashboard | Local-first Ollama-compatible agent, prompts, summaries, objectives/progress, persistent sessions, local HTTP/WebSocket dashboard |
| Supervision | Starts paused; explicit approval; ten-action budget; one action per observation; cleanup and failure pause |
| Policies | Protected mode default; explicit Squirrels-only owner mode verifies exact path and both ROM hashes, reports S1/S2 OWNER-WAIVED, keeps S3 mandatory |
| Offline tests | 72 Python tests (including 27 real-Lua mock scenarios), 19 Node tests; syntax/build checks passed; no failures or skips |
| Live emulator | **NOT RUN**; no mGBA launch, local-computer access or ROM/save/savestate reads/modifications in this task |
| Historical battery | v0.2 **5/8**, report preserved; no new live pass claimed |

The earlier audit-only/Phase-2 restriction was superseded by the owner's explicit
full-integration task. This authorises implementation, not live or unattended play
in this cloud session. No PR merge is authorised. Keep PR #1 a draft.

Remaining: verify Windows scripts, actual mGBA scheduling, ROM/symbol alignment,
input-pulse calibration, model availability/tool competence and real UI states.
Local pathfinding deliberately refuses special/unknown terrain. Hosted code
execution, automatic backup creation/pruning and reset are excluded. See
`UPSTREAM_INTEGRATION.md` for exact scope and limitations.

Next: review the diff/provenance, then perform the documented local Windows
verification under the selected policy. Do not treat fixture passes as emulator
or Pokédex-progress evidence. No trading or 380-species completion is claimed.
