# Decisions

| ID | Decision | Rationale / verification |
|---|---|---|
| D1 | A second FireRed ROM was selected for testing, but it is **not currently considered save-isolated**. | A `.sav` sidecar later appeared beside it and matched the protected save backups byte-for-byte. No gameplay until isolation is verified. |
| D2 | Re-check and relaunch mGBA as needed; do not assume the previous process is alive. | The emulator exited during the previous session; cause was not established. |
| D3 | Keep the bridge minimal rather than importing a large autonomous framework. | Smaller command surface is easier to audit and supervise. |
| D4 | Use discrete, frame-bounded button presses with automatic release. | Avoid indefinite held keys; T5 must verify release. |
| D5 | Use stock mGBA 0.10.5 Lua/socket scripting; no emulator fork planned. | Scripting/socket support was confirmed in the installed build. |
| D6 | Use the owner's local Ollama `qwen3.8:27b` model for the planned supervisor. | Owner preference; avoid unnecessary downloads. |
| D7 | One action per observation, maximum ten actions per sequence, human approval for irreversible actions. | Core supervision and auditability constraint. |
| D8 | Use a real Lua parser for syntax checks where available; mGBA load is still required for runtime validation. | Static parsing does not prove API compatibility. |
| D9 | Preserve the original save and its verified backups. | The backups remain local and are deliberately not in Git. |
| D10 | v0.3 uses a two-phase key queue to separate key-down from key-release. | Intended fix for the v0.2 T5 bug; verification pending. |
| D11 | A fresh mGBA process may be needed to load a new bridge version. | Bridge state is held in Lua locals; hot-patching was not established. |
| D12 | Use the Win32 native-menu helper as one method of opening the scripting console. | UI automation and SendKeys attempts were unreliable; helper success still needs end-to-end confirmation. |
| D13 | `cmd /c start` worked where PowerShell `Start-Process` failed in the prior environment. | Historical machine-specific observation; re-check before relying on it. |
| D14 | The public repository contains source and documentation only. | ROMs, `.sav` files, backups, `.mgbs` savestates, screenshots and bytecode were excluded. |
| D15 | Attribute adapted Lua bridge material to the upstream project under CC BY-NC 4.0. | See `THIRD_PARTY_NOTICES.md`; no blanket licence is applied to original FireRed-380 material. |

## Open questions

- **Q1 — first gameplay milestone:** default proposal is to receive/choose a starter; owner confirmation is still required.
- **Q2 — starter choice:** ask at the point of selection; valid FireRed choices are Bulbasaur, Charmander or Squirtle.
- **Q3 — scripting console:** Tools → Scripting is the expected route; the menu helper was written, but end-to-end opening was not confirmed.
- **Q4 — save protection:** the owner requires the protected `.sav` to remain unchanged. A savestate alone is not sufficient.
- **Q5 — emulator exit:** mGBA exited after a native-menu probe; cause remains unknown.
- **Q6 — v0.3 battery:** T5, T7 and T8 fixes remain unverified; require 8/8.
- **Q7 — save isolation:** decide and verify a separate disposable save path before any gameplay.
