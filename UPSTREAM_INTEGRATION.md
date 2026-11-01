# Pinned upstream integration

## Sources, licence and imported scope

Application source: [Clad3815/gpt-play-pokemon-firered](https://github.com/Clad3815/gpt-play-pokemon-firered)
at **9619b101d607ee79b68e1274174ac3b6eeb6ff06**. Work continues on
`codex/bridge-hardening` from **9a9630eea1da19154d84aad70d1bc71c03f06c3a**.
Use is personal and non-commercial, as authorised by the owner. Preserve CC BY-NC
4.0 attribution; the original licence is `third_party/upstream/LICENSE`.
`third_party/upstream/manifest.json` records all 72 imported source/reference files
and their original SHA-256 values. Differences from those hashes identify local
modifications, including whitespace-only normalisation; Git records the import and subsequent integration separately.

| Component | Integrated location and connection |
| --- | --- |
| Python package and symbols | `firered_bridge/`, root `pokefirered.sym`; existing reader imports are preserved |
| Memory transport | `firered_bridge/mgba_client.py` delegates exclusively to `workspace/src/bridge_client.py`; no port scanning, HTTP fallback or upstream retrying socket remains |
| Game-state builders | `state/builders.py` and `game_state.py` feed `/requestData`, Node formatters, prompts and dashboard |
| Player, party, PC, bag, save readers | `player/`; original PID/OTID decoding, quantity/money decryption and Pokédex flag interpretation retained |
| Text and dialogue | `text/` plus `ui/dialog.py`; decoded text and UI context feed state and prompts |
| Battle/menu/Pokédex/Fly Map | `ui/`; symbol callback recognition and factual region/flag metadata are wired without a decompilation checkout |
| World, collision, events, viewport | `world/` plus persistent fog-of-war; Node renders upstream minimap codes |
| Reference mappings | `game_data_firered/`; loaders resolve against the package root, not the caller's working directory |
| FastAPI application | `firered_mgba_bridge.py`; upstream routes retained with authorisation, single-action and cleanup wrappers; loopback only |
| Node agent and prompts | `server/src/core/gameLoop.js`, `ai/`, `prompts/`; original history, summaries, criticism, objectives and progress systems retained |
| Persistent sessions | `server/src/state/`, upstream memory/objective/history/session files are created locally, never imported from another run |
| Provider | `server/src/core/provider.js` maps upstream Responses-style history/events onto OpenAI-compatible chat completions; default local Ollama |
| Local path planning | `server/src/services/pathfinding.js` replaces paid hosted-code execution with conservative deterministic BFS |
| Dashboard | `frontend/` served by Node at `127.0.0.1:9885`; party, inventory, map, minimap, logs, objectives, model/token data and explicit supervision controls |
| Setup and startup | `scripts/`, `.env.example`, `config/`, exact Python lock and npm lockfile |

## Reference-data provenance review

The upstream symbol list and two JSON tables were committed as text in its initial
source history (`3d5c008`); no reproducible generator/build identity is supplied.
They are retained as published address/name/enum metadata under the upstream
notice, not as verified evidence about the owner's actual ROM. The symbol file
contains addresses, symbol types, sizes and names, **not executable ROM bytes**.
No compiled ROM, extracted image/audio, or proprietary asset bundle is included.
Pokémon names are their owners' trademarks; upstream's licence does not grant ROM
or game-media redistribution rights.

Four optional loader dependencies formerly pointed into the excluded decompilation
submodule. Its upstream-pinned revision is
**338ec9d956fcd39f4bbb361b444ded3eec8e9425**. We inspected only these text files:

- `data/layouts/layouts.json`: retain layout ID ordering only; discard file/graphics paths.
- `src/data/region_map/region_map_sections.json`: retain identifiers, names and numeric bounds only.
- `include/constants/flags.h`: derive numeric world-map flag offsets only.
- `src/region_map.c`: derive map-section/flag associations only; no C implementation is imported.

Derived factual tables are `layouts.json`, `region_map_sections.json` and
`world_map_flags.json`. Their source URLs/revision/hashes are recorded in
`third_party/upstream/reference_metadata.json`. This is not a wholesale import of
`pret/pokefirered`, its scripts, maps, game implementation or binary assets. No claim
is made that a third-party software licence covers Nintendo game assets. Future
asset imports need their own provenance review. Actual ROM/symbol alignment still
requires the subsequent Windows test.

## Deliberate modifications and exclusions

- **No replacement Lua bridge:** the only supported listener is our hardened
  `FireRedBridgeSocketServer_v0.3.lua`, reporting 0.3.1 on `127.0.0.1:8888`.
  No new Lua API or RAM-write/cheat surface was added. Archive versions are not
  startup targets. `memory/control.py`'s compatibility calls are interpreted in
  the Python adapter, not sent to an incompatible second listener.
- **No replayed inputs:** the hardened client handles framing, deadlines, socket
  cleanup and uncertain outcomes. The adapter never retries a failed mutation.
  It observes frame advancement and key release and always attempts cleanup.
- **Bounded control:** upstream smart-Lua movement is replaced with a short
  Python-dispatched pulse (8 frames for directions, 1 for facing, 12 for taps),
  followed by upstream observation/lock-transition checks. This does **not** claim
  exact one-tile movement equivalence; calibration awaits Windows verification.
  Requests carry one action, with at most ten actions per operator-approved
  sequence. The repeat-until-dialogue-end macro is reduced to a single A press
  in Node and rejected as a macro by the API.
- **No unattended startup:** the agent starts paused and has no approved action
  budget. Model/action failures pause it. Approval is explicit through the local
  dashboard. `scripts/Prepare-mGBA.ps1` prints the manual Lua-loading sequence;
  it deliberately never starts an emulator or probes a game file.
- **No backup access:** automatic upstream savestate generation and pruning are
  removed, not merely disabled by an environment default. The API reset endpoint
  reports unsupported. Optional recovery-state calls remain behind separate
  explicit opt-ins, confined to the hardened output sandbox, and are not invoked
  by the application or automated suite.
- **No hosted execution/data upload:** the upstream OpenAI container/code-interpreter
  pathfinder and temporary generated Python script are excluded. Local BFS only
  walks known free/grass tiles and refuses unknown/special terrain. Collision,
  spinner, water, boulder and ledge observations remain available; automated
  special-terrain path planning is a documented remaining limitation. Users can
  request bounded supervised controls instead.
- **Provider compatibility:** default Ollama uses native local HTTP with no API
  credential. Optional OpenAI uses a user-supplied key. Timeouts, malformed JSON,
  empty/truncated responses and parallel tool calls fail explicitly. We preserve
  the upstream event interface but buffer completions; true token-by-token model
  streaming/reasoning traces are not claimed. Vision is opt-in (`AI_VISION=1`)
  because model image support cannot be assumed.
- **Local UI:** removed Google Fonts requests; the static dashboard works with
  system fonts and no CDN. Services bind loopback. The existing unauthenticated
  local-process threat model remains; do not expose these ports remotely.
- Excluded: `.env` values, keys, histories, screenshots, minimaps, saves, savestates,
  upstream `mgba/` Lua implementation, `pokefirered` submodule, `server/tmp/`,
  node_modules, venvs, caches and build outputs. Upstream `.env.example` values
  were replaced with local-first, secret-free templates. `server/progress_steps.json`
  is a static milestone definition, not imported personal progress.

## Testing policies

**Protected mode remains the default.** The existing symmetric directory-isolation,
protected-hash, source/version and listener checks remain. A missing manifest locks
emulator access and actions; health/static UI still work.

**Owner-authorised mode is a separate opt-in** in both the manifest and invocation.
Only this exact pair is permitted:

- ROM: `C:\Emu\1636 - Pokemon Fire Red (U)(Squirrels).gba`
- Adjacent save: `C:\Emu\1636 - Pokemon Fire Red (U)(Squirrels).sav`
- MD5: `e26ee0d44e809351c8ce2d73c7400cdd`
- SHA-256: `3d0c79f1627022e18765766f6cb5ea067f6b5bf7dca115552189ad65a5c3a8ac`

Path validation precedes file access. The verifier opens **only** the approved ROM
read-only for hashing; it does not open its save, the second ROM/save, or backups.
The actual ROM and save destinations still need operator confirmation in mGBA;
no global mGBA configuration is changed. Owner mode requires neither a disposable
save directory nor protected-save hashes. S1 and S2 appear as **OWNER-WAIVED** with
`pass: null`, never as passed. S3 and T1–T8 remain mandatory, as do endpoint/version,
output-sandbox and all-keys-released checks. S3 is source review plus a regression
guard, not a formal proof. Mode-specific waivers are explicit in every report.

## Validation and current limits

The complete offline suite covers hardened transport, real Lua under mGBA doubles,
reader fixtures, party decryption, bag/money decoding, PC empty-slot interpretation,
map/collision/events, text, battle/menu/Pokédex/Fly recognition, API routes, owner
path/hash policy, waiver reporting, provider conversion/failures, local HTTP model
requests, dashboard HTTP/WebSocket connectivity, and persistent session reload.

Latest offline result: **72 Python tests** (including **18 Lua scenarios**) and
**13 Node tests** passed, with zero failures/errors/skips. Python compileall and
all 22 application/frontend JavaScript syntax checks passed.

Run `scripts/Test.ps1` after installation. Python test reports use new UUID-named
files in the OS temporary directory. The live battery writes separate reports to
the approved artifact directory; historical v0.2 evidence is unchanged.

No mGBA process was launched, no local computer was accessed, and no ROM/save/
savestate was read or modified during integration. Synthetic in-memory fixtures
are not emulator evidence. No live gameplay, exact movement timing, actual model
availability/tool competence, complete real-world UI coverage, symbol/ROM alignment,
Windows PowerShell execution, or 380-species progress is claimed. Subsequent local
Windows verification and PR review are required before operational use.
