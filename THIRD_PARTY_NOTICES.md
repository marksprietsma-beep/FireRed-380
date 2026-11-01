# Third-party notices

## FireRed mGBA Lua bridge

The Lua bridge implementation in:

- `workspace/archive/legacy/FireRedBridgeSocketServer_v0.1_legacy.lua`
- `workspace/src/FireRedBridgeSocketServer_v0.2_fixed.lua`
- `workspace/src/FireRedBridgeSocketServer_v0.3.lua`

contains material adapted from **GPT Plays Pokemon FireRed**, repository:
<https://github.com/Clad3815/gpt-play-pokemon-firered>

The upstream repository publishes its material under **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**:
<https://creativecommons.org/licenses/by-nc/4.0/>

Attribution: “Based on GPT Plays Pokemon FireRed. Original source: https://github.com/Clad3815/gpt-play-pokemon-firered. Licensed under CC BY-NC 4.0.”

The FireRed-380 versions are modified adaptations. Changes include reducing the command surface, adding local-loopback binding in the later versions, restructuring the command parser and connection handling, adding bounded button presses, and implementing the v0.3 two-phase key-release fix and additional commands.

This notice applies to the identified adapted bridge files only. It does not place all original FireRed-380 material under CC BY-NC 4.0.

## Integrated upstream application (personal, non-commercial use)

The Python `firered_bridge` package and API, Node `server`, dashboard `frontend`,
prompts, and text reference tables are adapted from the same project at commit
`9619b101d607ee79b68e1274174ac3b6eeb6ff06`, under CC BY-NC 4.0. The upstream licence
is preserved verbatim at `third_party/upstream/LICENSE`; the original-file hashes
are recorded in `third_party/upstream/manifest.json`. Integration modifications
are documented in `UPSTREAM_INTEGRATION.md`. Attribution: Based on GPT Plays
Pokemon FireRed, https://github.com/Clad3815/gpt-play-pokemon-firered.

The symbol list and JSON tables are plain-text addresses, identifiers and mappings
published in that snapshot. They contain no ROM bytes, graphics, audio or compiled
code; they are reference metadata, not a redistributed game. Pokémon names remain
their owners' trademarks. The upstream licence does not grant rights to any ROM or
Nintendo game assets. No `pret/pokefirered` submodule or extracted game media is
included. These reference tables still require validation against the actual ROM.
