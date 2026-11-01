# Risk log

| Risk | Rating | Mitigation | Status |
|---|---|---|---|
| Protected save may be modified by the test ROM | **CRITICAL / BLOCKER** | A `.sav` sidecar beside the test ROM was byte-identical to the protected save backups. Establish a separate disposable save path and verify it before any gameplay. | Open; no gameplay |
| Bridge v0.3 may regress or fail to load | **MED** | Load only after save isolation; verify version and loopback listener; run full battery. | Untested |
| v0.2 timed key release bug | **HIGH** | v0.3 two-phase release is intended to fix it; verify T5 live. | Fix unverified |
| Intermittent connection failure | **MED** | Battery records the failing error; investigate evidence before changing server code. | T7 unverified |
| Multi-command framing/client bug | **MED** | `call_raw` join/encode fix is present; verify T8 live. | Fix unverified |
| Emulator/menu automation instability | **MED** | Verify the console actually opens; use GUI fallback if the Win32 helper fails. | Previous end-to-end open unconfirmed |
| LLM misreads game state or issues unsafe input | **MED** | One action per observation, explicit verification, maximum ten actions per sequence, human approval for irreversible actions. | Future phase |
| Public repository accidentally receives game/private assets | **HIGH** | `.gitignore` excludes ROMs, saves, savestates, screenshots, caches and local secrets; review every staged change. | Controls added |

No risk should be downgraded merely because a fix has been written. Update status only after observed verification.
