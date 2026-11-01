# Project FireRed 380 — Hermes + Qwen autonomous Pokédex agent

**Document type:** implementation brief and operating instructions  
**Version:** 1.0 — 16 October 2026  
**Status:** approved goal; implementation not yet verified  
**Owner's platform:** Windows 11, ASUS ROG Strix SCAR 16 G634JZR, NVIDIA RTX 4080 Laptop GPU (12 GB VRAM), currently 16 GB system RAM  
**Preferred agent:** Hermes Agent using local Ollama/Qwen3.5, initially the already-installed 9B model; 27B may be tried later if it runs reliably  
**Main game:** Pokémon FireRed, original Generation III GBA release, with legally supplied ROM and save files

> **Your assignment as Hermes:** Read this entire file, treat it as the approved project specification, independently inspect the existing environment and reference implementations, produce a concrete plan, and **start executing the smallest safe implementation steps**. Do not merely paraphrase this brief or claim work is complete when it has not been tested. Continue through the next unblocked milestone within the safeguards below. Pause and ask the owner only for missing essential materials, permission-sensitive actions or genuine blockers.

---

## 1. Mission and definition of success

Build a Windows-native, locally operated agent that learns to **play the original Pokémon FireRed and earn the National Pokédex completion certificate by registering the 380 required species as owned/caught**, through legitimate in-game methods and emulated trading across official Generation III games.

The objective is **not** merely to defeat the Elite Four, and **not** necessarily a living Pokédex with all 380 specimens simultaneously in storage. Registration in the **primary FireRed save** is the authoritative measure; the end condition is the game's actual certificate/recognition, not just an externally calculated number.

The six species not required for the FireRed/LeafGreen National certificate are **Mew, Lugia, Ho-Oh, Celebi, Jirachi and Deoxys**. This is a 380-of-386 **specific-species** requirement, not “any 380 species”. Verify details against the actual original-game version and reliable references rather than assuming a guide or emulator has the correct flags.

The agent may obtain needed species via legitimate captures, evolution, breeding, fossils, gifts, in-game trades, conventional link trades between separately played official Generation III versions, and repeat playthroughs. Completing story milestones is allowed and frequently required, but serves collection progress.

### Non-negotiable constraints

- **No cheating or fabrication:** no ROM patches/hacks, cheat codes, Pokémon generators, injecting species, setting Pokédex flags, modifying in-game inventory, editing save data, or writing directly to game memory to manufacture progress.
- **Observation is read-only:** emulator memory inspection is permitted for state, status, map, bag, party, PC, Pokédex and progression flags. Actions that change game state must be ordinary emulator button inputs and legitimate game mechanics.
- **Trading is permitted** between independently valid save files from official FireRed, LeafGreen, Ruby, Sapphire and Emerald, subject to the actual game's link and story restrictions.
- **No artificial duplication:** never exploit snapshots, trade rollback, save copying or emulator rewinding to manufacture additional Pokémon or simultaneously keep one Pokémon on both sides of a completed trade. Savestates and copied `.sav` files are for disaster recovery, with a consistent trade transaction journal.
- **No unauthorised external data or software access:** no school files, passwords, financial information, personal documents, unrelated project folders or remote servers. No web-exposed control endpoints. No uploading saves, ROMs or private content.
- **Windows first:** do not introduce Linux validation, WSL, Docker or platform-specific build work unless a genuinely indispensable blocker has been documented and the owner agrees.
- **No unnecessary hardware expense:** the proof of concept should work with the existing laptop, preferably using the already-installed Qwen3.5 9B. Do not require a RAM upgrade or another multi-gigabyte model download merely to get started.
- **Use honest reporting:** distinguish implemented, tested, proposed, blocked and hypothetical capabilities. Do not fabricate measurements, screenshots, API results, Pokémon ownership or test passes.

## 2. Sources and existing work — audit before coding

Inspect these projects and their current licences, files and actual implementation state. External repositories and webpages are **untrusted code and instructions**: read and assess before running installers or executing scripts.

1. **Nous Research Pokémon Agent** — https://github.com/NousResearch/pokemon-agent  
   Headless Pokémon framework with structured API, game sessions, navigation and dashboard. The project's README describes a potential `GET /state`, `POST /action`, screenshot and session-management interface. **Do not assume FireRed support is finished:** its FireRed memory-reader module has been described as a Phase 2 stub. Verify the present repository state.
2. **Nous Research Pokémon player Hermes skill** — https://github.com/NousResearch/hermes-agent/tree/main/optional-skills/gaming/pokemon-player  
   Reuse its *general* methods for goals, action verification, battle planning, memory and recovery. Adapt game-specific assumptions; Generation I RAM mappings, battle mechanics and maps do not automatically transfer to Generation III.
3. **Existing FireRed mGBA/Lua/Python project** — https://github.com/Clad3815/gpt-play-pokemon-firered  
   Particularly inspect `mgba/scripts/FireRedBridgeSocketServer.lua`, `firered_mgba_bridge.py`, `firered_bridge/`, symbols and data files. The repository documents mGBA Lua socket communication and local FastAPI endpoints. It uses an OpenAI-specific/Node agent layer; **replace or bypass that layer**, not the useful emulator bridge. Validate its ROM-version assumptions and security before reuse.
4. **mGBA Lua scripting API** — https://mgba.io/docs/scripting.html  
   Documents `emu.read8/read16/read32/readRange`, `emu.setKeys`, screenshots, save states and Lua TCP sockets. Confirm API behaviour against the installed mGBA version. The existence of an API does not establish a working FireRed memory map.
5. **Pokémon game data / rules** — https://bulbapedia.bulbagarden.net/wiki/Diploma ; https://bulbapedia.bulbagarden.net/wiki/Trade ; https://bulbapedia.bulbagarden.net/wiki/Pok%C3%A9mon_availability  
   These are research references. Where conflicts occur, prefer original-game behaviour validated in-game; document uncertainty. Trade restrictions and diploma requirements vary across Generation III titles.

Check repository commit/version dates, licences, Windows support, dependency lists, tests, and existing features. Cite source URLs in your technical notes. **Re-use tested components, but do not import a large framework without evaluating whether a thin adapter is simpler.**

## 3. Target architecture

```text
Owner / Hermes CLI or Desktop
             |
             v
Hermes + Ollama (Qwen3.5)
  - planning and tool decisions
  - persistent factual memory + experience notes
  - objective ledger and bounded action cycles
             |
             v
Local FireRed Agent API (Python; 127.0.0.1 only)
  - read structured game state
  - bounded controller commands
  - screenshots, checkpoints, transactions
  - per-instance ID / ROM fingerprint
             |
             v
Lua TCP adapter inside mGBA
  - read-only memory observations
  - emulator button presses/frame stepping
  - screenshot/save/restore hooks
             |
             v
mGBA + original Gen III ROM(s)
  - FireRed primary save
  - separate donor-game save instances for trades
```

Prefer **API/tool control** over slow desktop mouse automation. Desktop Computer Use may be used to launch/inspect windows or recover from failures, but the primary game loop should use structured observations and controlled GBA inputs. Do **not** make model actions depend on a fragile fixed screen position when a native emulator command is available.

The local bridge should expose a deliberately small versioned interface, preferably retaining compatibility with useful Pokémon Agent endpoint conventions where practical:

- `GET /health` — emulator connection, ROM identity, version, bridge status; no secrets.
- `GET /state` — a structured, clearly documented observation; indicate unavailable fields as `null`/`unknown`, never invent them.
- `GET /screenshot` — current frame (PNG) or explicit unsupported response.
- `POST /action` — a named button/action with validated maximum held frames, timeout and single-instance target.
- `POST /control/pause` and `/control/resume` — immediate operator control.
- `GET /progress` — confirmed Pokédex records and milestone ledger.
- Optional later: `POST /checkpoint`, `GET /events`, `GET /objectives`, separate multi-instance trade orchestration.

Bind listeners to `127.0.0.1`. Validate input and cap frame count per command; implement an operator stop/pause. Add a lightweight health check, bounded retries, reasonable timeouts and logs without containing sensitive local paths. For multiple emulator instances, use distinct process IDs, socket ports and unique save paths; never send actions to the wrong game.

### Minimum observation schema (illustrative, not an assertion of current implementation)

```json
{
  "schema_version": 1,
  "instance_id": "firered-primary",
  "rom": {"title": "Pokemon FireRed", "region": "USA", "revision": "unverified", "sha256": "..."},
  "timestamp": "ISO-8601",
  "player": {"map": null, "x": null, "y": null, "facing": null},
  "mode": "unknown",
  "party": [],
  "bag": null,
  "badges": null,
  "pokedex": {"owned_count_verified": null, "owned_species_ids": null},
  "battle": null,
  "screenshot_available": false,
  "confidence": {"source": "memory/screen", "validated": false}
}
```

First prove each field against visible game evidence and/or documented game structures, rather than treating plausible-looking memory values as truth. Determine the exact ROM edition/revision through a fingerprint. Never use hardcoded memory offsets unless appropriate for that verified revision; handle unavailable or unstable addresses conservatively.

## 4. Collection intelligence, tracking and legal acquisition

Create a persistent **species acquisition ledger**, not just a scalar counter. Each of the 380 required National species must have a record with fields such as:

- National Dex number, species name, and required-for-certificate boolean.
- **Authoritatively caught/owned registered in primary FireRed save?** Verified by in-game state or validated reader; observed timestamp; confidence/source.
- Available sources: game version, route/area, encounter conditions, gift, fossil, evolution, breeding or trade, with evidence/reference.
- Prerequisites: badge, HM, progression flag, location access, time-based requirement, item, level, friendship, trade item, relevant donor save.
- Current pursuit state: `unresearched`, `known_missing`, `available_now`, `requires_progression`, `requires_trade`, `in_progress`, `verified_acquired`, `blocked`.
- Where useful, donor-game/instance provenance and trade transaction ID.

**Registration, not a living dex:** a species is counted only when the **primary FireRed game's Pokédex actually registers it as owned**. Do not count merely seeing it, possessing it on a donor save, or predicting that a trade should register it.

Implement acquisition planning as a dependency graph rather than a fixed species order. The agent should prefer low-risk, accessible goals, group geographically nearby opportunities, preserve evolution items, ensure access to required breeding and trading, and only tackle difficult repeated-playthrough goals when prerequisites are met.

Known progression dependencies that must be verified and modelled include:

- FireRed National Dex upgrade after relevant regional Pokédex and story milestones.
- Celio's Network Machine and the Ruby/Sapphire key-item quest for Hoenn-game trading.
- Version exclusives and starter evolution lines across multiple games.
- Trade evolutions, item-based evolutions, friendship/time requirements and breeding.
- Johto starters obtainable through repeated qualifying Emerald runs (verify all requirements before scheduling them).
- Starter-dependent legendary beast encounters requiring separate FireRed/LeafGreen runs (verify conditions).
- Actual multi-instance link-cable trading support for installed emulator, as this is a **technical milestone**, not an assumed feature.

A species-by-species source audit should decide the **minimum combination** of FireRed/LeafGreen/Ruby/Sapphire/Emerald and repeat runs. Do not assume Ruby/Sapphire/Emerald/LeafGreen are already installed or that every one is required; the owner supplies legal game files as needed. If the plan reaches a legitimately unobtainable requirement under the allowed game set, identify it explicitly rather than quietly adding cheats or an unauthorised ROM.

### Learning versus memory

The LLM's weights do **not** update through play. Improvement should occur through:

1. **Verified game memory:** canonical state and progress ledger, written from actual observations.
2. **Experience log:** attempted objective, hypothesis, action sequence, outcome and what was learned; distinguish fact from speculation.
3. **Reusable procedures:** validated, compact Hermes skills for successful repeated actions (menu navigation, healing, obtaining Poké Balls, tracking routes, trading).
4. **Evaluation:** measurable objective progress, fewer stuck loops, better battle win rate, lower wasted actions and fewer invalid tool calls.

Never promote an unverified guess to canonical memory. Automatically prune duplicate/repetitive logs and keep the context budget manageable. Never store raw ROM data in Hermes conversational memory.

## 5. Staged plan — start with a minimum working bridge

### Phase 0 — Pre-flight audit and safe setup (START HERE)

1. Determine current working directory; locate this file; define **project root as its parent `instructions` directory's parent**, unless the owner provides another location.
2. Record installed versions and readiness of: Windows, Hermes, Ollama, Python, Git, mGBA, required packages, and available local ROM/save **without opening unrelated files**.
3. Create a dedicated `workspace/` directory **next to `instructions/`** and subdirectories for `src/`, `tests/`, `docs/`, `state/`, `logs/`, `backups/`, `third_party/`. Do not mix temporary code with the instructions folder. Keep ROM/save locations configurable; don't commit them to Git.
4. Check whether the owner has supplied an original FireRed ROM and save. Do not download copyrighted ROMs or solicit credentials. If absent, proceed with mocks and audit work; ask for a lawful local file only when a live test needs it.
5. Inspect the three reference projects and write `workspace/docs/REUSE_AUDIT.md`: components, verified status, Windows viability, licences, known blockers, likely integration strategy. Do not execute fetched code before review.
6. Write `workspace/docs/PLAN.md` and `workspace/docs/STATUS.md` with the exact current state and next three concrete steps. Create an initial Git repo if appropriate, excluding saves/ROMs/secrets.

**Acceptance:** clear environment report, architecture decision, reusable components identified, workspace created, next action chosen. No model download or huge installation should be required merely for Phase 0.

### Phase 1 — One working emulator command and observation

1. Verify mGBA version with Lua capability; load a legally supplied FireRed ROM in a separately backed-up emulator instance.
2. Adapt a **minimal** Lua socket bridge, preferably from the existing FireRed repository. Bind to loopback, log its chosen port and verify connection from Python.
3. Prove **one harmless controller input** (such as a title-menu button), observe the visible result, and capture one screenshot.
4. Read at least **one stable, game-specific state field** (e.g., map identifier or validated party HP) from read-only memory and cross-check it against the game display. If a field is not yet reliable, report that and do not fake success.
5. Expose local `/health`, `/state` and `/action` endpoints; add command validation, timeout and pause.
6. Add automated tests with mocks for command validation, transport failure, timeout, unavailable state, wrong instance and no state mutation beyond controller action.

**Acceptance:** live, reproducible emulator-to-Lua-to-Python round trip on Windows; screenshot; one verified field; action produces observed result; failures are safe. Include commands and logs in `workspace/docs/PHASE1_REPORT.md`.

### Phase 2 — Reliable read-only FireRed state

- Expand verified observation to player coordinates and map, mode/dialogue/battle detection, party information, HP/moves/status, bag, badges, and Pokédex owned flags; PC storage where feasible.
- Validate Gen III Pokémon substructure decryption and game version-specific offsets with fixtures and visible observations.
- Implement basic screenshot fallback for fields not verified via RAM.
- Record provenance for each field and tolerate transient loading/transition states.

**Acceptance:** repeated observation tests across overworld, menu and battle; known failures detected rather than silently misreported.

### Phase 3 — Hermes tool adapter and controlled play

- Expose a small, well-described skill/tool interface to Hermes; load the installed Pokémon Player skill for general guidance but **override unsupported Generation I assumptions**.
- Start with the **existing Qwen3.5 9B** model; assess tool reliability and latency rather than assuming a 27B model is required. If the Hermes runtime insists on a context too large for current RAM, report measured limits and request a decision instead of crashing/retrying indefinitely.
- Provide `observe → decide → one bounded action → verify`, with a rolling short objective and stuck detector.
- Start supervised: title screen, initial dialogue, navigation, first battle, Poké Ball purchase, first verified capture.
- At first, limit autonomous sequences to **10 game actions** before summarising and requesting approval. Increase only after repeated clean results.

**Acceptance:** at least one gameplay milestone achieved with actual tools, verified by new game state, without hidden manual intervention.

### Phase 4 — Pokédex planning and collection loop

- Populate authoritative species source/prerequisite database, then incrementally verified caught flags.
- Add acquisition task queue, resource/party planning, navigation, battle/encounter management, capture confirmation, healing and stuck recovery.
- Record progress each session; monitor newly owned species, elapsed game time, number of actions and failed attempts.
- Never autonomously discard rare Pokémon, release Pokémon, delete save files, spend irreplaceable evolution items or reset a main save without explicit approval.

**Acceptance:** at least 10, then 30 distinct species verified registered in primary FireRed save, with durable state surviving an agent restart. (Do not assert these are already done.)

### Phase 5 — Multi-save, multi-game trading

- First independently verify mGBA link cable/trading between two correctly configured, separately saved instances; do not assume computer-use scripting or sockets can magically establish a valid link.
- Implement a **two-phase trade journal**: pretrade snapshots and identities of both save files; pending species and parties; operator approval; actual in-game trade; post-trade verification on **both** sides; new backup; mark committed only after verification.
- Protect against savestate rewind that duplicates species or desynchronises saves. If uncertain after a crash, quarantine the transaction and request owner review.
- Introduce LeafGreen, Emerald, Ruby and Sapphire as prerequisites require, using legally supplied copies and separate save identities.

**Acceptance:** a real version-exclusive or trade-evolution transaction is verified in-game on both sides and, where relevant, registered in primary FireRed.

### Phase 6 — Long-running collection, evaluation and certificate

- Operate with staged autonomy, bounded sessions, validated backups, scheduled checkpoints, temperature/memory-aware pauses, and explicit stop conditions.
- Pursue the dependency graph until **each of the 380 required species is verified as owned on primary FireRed**.
- Visit the correct in-game diploma giver and document actual certificate presentation. Only then mark the objective complete.
- Provide a final ledger, list of completed trade transactions, save backups and retrospective of strategies improved through experience.

## 6. Operating limits and recovery rules

- **No unattended marathon during initial setup.** The owner's laptop has previously shown unexpected shutdowns, even though recent GPU temperatures during Qwen9B inference were satisfactory.
- Limit resource-heavy tasks; pause if there are power interruptions, repeated hangs, dangerous temperatures, high memory pressure, or multiple failed tool calls. Do not launch simultaneous ComfyUI workloads or 27B Ollama sessions during early tests.
- Maintain **system-managed Windows paging**, and avoid repeated forced reboots as a workaround.
- Keep backups timestamped and labelled with instance/ROM fingerprint. Preserve the last known-good in-game `.sav` separately from savestates.
- Add an **emergency stop** that prevents new controller commands immediately. Stop after five consecutive action failures, three unchanged-state navigation cycles, or evidence that state readings are inconsistent; report the blocker and recovery recommendation.
- For irreversible in-game decisions affecting collection planning (starter choice, legendary capture decisions, reset/new game, permanent move deletion, rare consumables, trades), ask the owner unless the relevant choice was explicitly approved and documented.
- Avoid unnecessary browser automation and wide filesystem permissions. Keep dependencies within a Python virtual environment; pin versions once known.
- Protect save files against Git commits and cloud-sync conflicts; no public posting of ROMs, `.sav`, tokens or private logs.

## 7. Documentation and evidence requirements

Maintain these files as work progresses:

```text
instructions/
  FIRERED_POKEDEX_AGENT_SPEC.md  # this document; owner-approved scope
workspace/
  docs/
    PLAN.md                 # phases, tasks, dependencies
    STATUS.md               # current milestone, blockers, actual test results
    REUSE_AUDIT.md          # upstream project assessment and licences
    ARCHITECTURE.md         # bridge protocol and state schema
    GAME_RULES.md           # verified trade/progression/certificate rules
    RUNBOOK.md              # Windows start/stop commands, recovery
  src/                      # bridge, Lua, tools, agent adapter
  tests/                    # unit + emulator integration checks
  state/                    # authoritative species ledger; no ROMs committed
  logs/                     # bounded JSONL; local only
  backups/                  # separately labelled and protected saves
  third_party/              # reviewed reference code and licences
```

Each major milestone must include: exact commands used, what was observed, pass/fail, unresolved assumptions, files changed, save-file impact, current model and context configuration, and what to do next. Use screenshots, emulator logs and machine-verifiable state where possible.

Keep `workspace/docs/STATUS.md` readable in under two minutes: **Done / In progress / Blocked / Next action**. If Hermes restarts, read STATUS first rather than rereading all chat history.

## 8. Start-work instructions for Hermes

**Do these now:**

1. Confirm you have read this specification and identify its actual filesystem location.
2. Inspect the installation and available files **within the defined workspace only**; don't guess paths or claim the emulator or ROM exists.
3. Create the workspace, audit the reference repos, and write `PLAN.md`, `REUSE_AUDIT.md` and `STATUS.md`.
4. Choose the **smallest runnable Phase 1 proof of concept**, preferably reusing the FireRed Lua socket bridge, and begin implementing and unit-testing it.
5. If a real ROM is not supplied, continue with transport mocks and ask the owner for the ROM's local path only when needed for the live test.
6. Report a concise status when a phase finishes or a genuine owner decision is required. **Do not stop merely because the full 380-species goal is large.** Make incremental, tested progress.

### Required initial reply

After pre-flight work, report:

- Environment detected (not presumed).
- Upstream components worth reusing versus replacing, with reasons.
- Actual files created/changed.
- Tests genuinely executed and their results.
- The current blocker, if any, and **one specific** action requested from the owner.
- The next concrete implementation step.

**You are an implementing agent, not just a consultant. Start Phase 0 now and proceed to Phase 1 wherever safe and feasible.**
