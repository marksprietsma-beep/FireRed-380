# Bridge hardening candidate 0.3.1

This is Task 2 reliability work, not Phase 2. No emulator was launched and no
ROM, save or savestate was modified. The only live evidence remains the historical
v0.2 5/8 report at `workspace/state/battery_report.json`, preserved byte-for-byte.
Version 0.3.1 has offline mock coverage, not a Windows/mGBA pass.

## Changes and compatibility

- Existing command names, `<|END|>` framing, `<|OK|>`/`<|ERROR|>` replies, decimal
  read replies, hexadecimal key masks and semicolon-separated keys remain.
  Unquoted CSV and legacy whitespace requests still work. The client now sends
  UTF-8 with quoted CSV arguments; doubled quotes are parsed correctly. Markers
  and control characters in arguments are rejected before transmission.
- `bridge.version` now returns `0.3.1`; `bridge.info` and `bridge.outputDir` are
  additive readiness checks. The filename remains `_v0.3.lua` to preserve paths.
- A request has a total connection/send/receive deadline, not just an idle timeout,
  plus a 128 KiB request/response ceiling. EOF, incomplete responses, excess replies
  in a received chunk and bad UTF-8 are explicit errors. Sockets close in `finally`.
- Only explicitly allowlisted read-only single calls retry. Every other command,
  including unknown commands, screenshot/state operations, clearAll and shutdown,
  is attempted once. Raw batches never retry. `BridgeUncertainError` means the
  action may already have executed: observe and reconcile; never blindly replay.
  No end-to-end exactly-once guarantee or server deduplication is claimed.
- Holds require integer durations 1–300 frames (default 12), with at most 32 queued
  holds. Duration begins when the frame callback applies the input. Per-key owner
  counts prevent one expiring hold from clearing another's shared key. clearAll
  cancels pending and active holds. A frame-counter rewind clears the queue.
- Frame callback installation must succeed before listening. API absence,
  registration failure, listen failure and runtime callback exceptions fail closed.
  Shutdown clears/verifies all keys, sends `bye<|END|>` before disconnecting, then
  closes sockets and calls `callbacks:remove(id)`. clearKeys has a setKeys fallback.
  Removal failures are logged, and any surviving callback becomes inert. Transport
  failures cannot guarantee ACK delivery; held keys are still cleared on shutdown.
- File commands accept **basenames only**, in an explicitly configured absolute
  Windows output directory. `.png` is required for screenshots; `.mgbs` for state
  operations. Paths, traversal, ADS, Windows device names, control characters,
  Unicode filenames and existing output files are rejected. File-check errors
  other than ENOENT fail closed. Screenshot output is verified because mGBA can
  silently fail to open it. State commands require a separate console opt-in;
  state flags are explicitly zero, excluding savedata and cheats.
- The live battery is import-safe and opt-in, validates version/readiness, uses
  actual frame advancement for T5, checks all ten keys for T6, disables retries
  for T7 and verifies ordered success/error/success framing in T8. Cleanup runs
  in finally blocks. Failure/skipped checks cannot produce an overall pass.
  Reports use fresh UUID names and exclusive creation outside the checkout.
  Output and disposable-save directories must be disjoint from each other and
  the checkout. Neither may contain, equal or be inside a protected-save
  directory; all directory-containment checks run in both directions.

## mGBA API evidence

Checked the official **0.10.5** source, commit
`26b7884bc25a5933960f3cdcd98bac1ae14d42e2` (not current online docs for another version):

- [Lua socket adapter](https://github.com/mgba-emu/mgba/blob/26b7884bc25a5933960f3cdcd98bac1ae14d42e2/src/script/engines/lua.c):
  bind/listen return a socket or `1` on success, receive returns `nil,error`,
  AGAIN is transient, `send(data,i,j)` returns the last byte index, socket events
  poll once per frame, and closing a socket removes its own frame callback.
  Standard Lua libraries, including `io`, are opened by the engine.
- [Callback manager](https://github.com/mgba-emu/mgba/blob/26b7884bc25a5933960f3cdcd98bac1ae14d42e2/src/script/stdlib.c)
  and [context](https://github.com/mgba-emu/mgba/blob/26b7884bc25a5933960f3cdcd98bac1ae14d42e2/src/script/context.c):
  add takes event/function and returns a positive numeric ID; remove takes ID only.
- [Core bindings](https://github.com/mgba-emu/mgba/blob/26b7884bc25a5933960f3cdcd98bac1ae14d42e2/src/core/scripting.c):
  currentFrame/getKeys return integers; addKeys/clearKeys/setKeys are mask operations.
  screenshot has no return and silently returns when VFileOpen fails. State file
  methods return bool and accept flags. saveStateFile defaults to ALL;
  loadStateFile defaults to ALL minus SAVEDATA, which is why explicit flags are used.
- [Serialization flags](https://github.com/mgba-emu/mgba/blob/26b7884bc25a5933960f3cdcd98bac1ae14d42e2/include/mgba/core/serialize.h)
  and [save directory selection](https://github.com/mgba-emu/mgba/blob/26b7884bc25a5933960f3cdcd98bac1ae14d42e2/src/core/directories.c):
  `savegamePath` selects a separate save directory; when unset, the ROM directory
  can be used. A different ROM pathname alone does not establish save isolation.

## Offline verification (no game assets)

From the checkout root, Python 3.10+ and Lua 5.3+ are sufficient. No pip packages
are required. Put `lua` on PATH or set `LUA_BIN` to its full executable path.
An existing `texlua` interpreter is also supported; it was used in this cloud task.
Lua is a development test tool, not an application dependency.

```powershell
$env:LUA_BIN = 'C:\Tools\Lua\lua.exe' # omit if lua is already on PATH
python .\workspace\tests\run_mock_tests.py
python -m py_compile .\workspace\src\bridge_client.py .\workspace\tests\test_bridge_battery.py .\workspace\tests\run_mock_tests.py .\workspace\tests\mock\test_bridge_client.py
```

The runner executes the complete Python suite, including a subprocess that loads
the real Lua source against mGBA/socket doubles. Missing Lua is a failure, not a
skip. It writes a new `firered-mocks-<UUID>.json` in the OS temporary directory.
Expected current result: **41 Python tests passed**, including **18 Lua scenarios**;
zero failures, errors or skips. Simulated battery failures printed during mock
checks are expected assertions of failure reporting, not live emulator results.

## Exact local Windows/mGBA verification procedure

Do not execute this procedure until the owner approves it and isolation is proven.
Keep all original ROMs, saves, backups and recovery savestates untouched. Do not
load the omitted historical checkpoint or run these tests against the primary save.

1. In a separate disposable mGBA 0.10.5 configuration, select the owner-approved
   disposable save directory under **Settings → Paths** (`savegamePath` internally).
   Confirm the effective ROM/save destination before allowing emulation to advance.
   The owner must provide the lawful local ROM and disposable `.sav`; this runbook
   does not create or copy game assets. Ensure protected originals/backups are in
   separate directories and inaccessible for writes by the test process where
   practical. Do not assume a savestate or `.gitignore` provides this protection.
2. Review the S1–S3 conditions in `TEST_PROTOCOL.md`. Verify the actual active save
   destination from the local mGBA configuration and, preferably, Windows file-I/O
   tracing. Record protected original/backup SHA-256 values **before launch** and
   again before the battery. A hash proves identity, not path isolation.
3. Create a new empty **ASCII-path** artifact directory outside the checkout and
   outside protected save/backup directories, e.g. `C:\FireRed380-test\run-001`.
   Do not use symlinks, junctions, reparse points, shared/cloud-synced directories,
   or any directory another process can modify. Choose a new directory each run.
4. Start the isolated mGBA instance with the intended ROM, verify **Help → About**
   shows 0.10.5, then use **Tools → Scripting**. Set these globals before loading:

   ```lua
   FIRERED_BRIDGE_OUTPUT_DIR = "C:/FireRed380-test/run-001"
   FIRERED_BRIDGE_ALLOW_STATES = false
   dofile("C:/path/to/FireRed-380/workspace/src/FireRedBridgeSocketServer_v0.3.lua")
   ```

   Require the READY line for `127.0.0.1:8888 v0.3.1`. Do not hot-load over an
   existing bridge. Any callback/release error is a stop condition.
5. In PowerShell at the checkout root, identify the listener and hash the exact
   bridge source. These commands only inspect state:

   ```powershell
   Get-NetTCPConnection -LocalPort 8888 -State Listen | Format-Table LocalAddress,LocalPort,OwningProcess
   Get-Process -Id <OwningProcess> | Select-Object Id,Path
   (Get-FileHash .\workspace\src\FireRedBridgeSocketServer_v0.3.lua -Algorithm SHA256).Hash.ToLowerInvariant()
   Get-FileHash 'C:\protected\original.sav' -Algorithm SHA256
   # Repeat Get-FileHash for every protected backup, using its actual local path.
   ```

   Confirm the process path is the intended mGBA executable. Create a local JSON
   manifest **outside the checkout/output directory** using the actual values:

   ```json
   {
     "owner_approved_isolation": true,
     "active_save_path_verified_in_mgba": true,
     "host": "127.0.0.1",
     "port": 8888,
     "bridge_version": "0.3.1",
     "bridge_sha256": "<lowercase source hash>",
     "mgba_pid": 1234,
     "mgba_executable": "C:/path/to/mGBA.exe",
     "output_dir": "C:/FireRed380-test/run-001",
     "disposable_save_dir": "C:/FireRed380-test/disposable-save",
     "active_save": "C:/FireRed380-test/disposable-save/Pokemon - FireRed Version.sav",
     "protected_files": [
       {"path": "C:/protected/original.sav", "sha256": "<lowercase original hash>"},
       {"path": "C:/protected-backups/backup.sav", "sha256": "<lowercase backup hash>"}
     ]
   }
   ```

   Include **all** protected backups. Set attestation booleans only after verifying
   those facts. The runner cannot discover mGBA's active save filename through its
   scripting API; attestation is an explicit prerequisite, not automated proof.
6. Keep mGBA unpaused at normal speed and do not press physical controller keys.
   Execute the battery once:

   ```powershell
   python .\workspace\tests\test_bridge_battery.py --safety-json 'C:\FireRed380-test\safety.json'
   $LASTEXITCODE
   ```

   Require exit 0, T1–T8, key-release verification and all hash checks passing.
   The runner independently checks the OS listener's address/port/PID/executable
   with Get-NetTCPConnection, then checks version/callback/path-policy replies.
   It rejects wildcard or additional listeners on 8888. It refuses unsafe manifests
   before opening a TCP connection. The test sends only two bounded input actions.
   Inspect the new UUID-named JSON and PNG in run-001; manually compare the image
   with the actual emulator display. No savestate command is used by this battery.
7. After the report and key-release checks, exercise clean shutdown from the same
   checkout in PowerShell (only after the earlier safety gates):

   ```powershell
   python -c "import sys; sys.path.insert(0, 'workspace/src'); from bridge_client import BridgeClient; print(BridgeClient(retries=0).shutdown())"
   Get-NetTCPConnection -LocalPort 8888 -State Listen -ErrorAction SilentlyContinue
   ```

   Expect `bye`, no listener, and no held inputs in mGBA. Any lost acknowledgement
   is an uncertain result: do not automatically replay input commands. If cleanup
   fails, pause mGBA immediately and investigate manually before continuing.
   Recheck every protected hash after clean emulator shutdown, since save writes
   can occur later than the battery's final hash check. Record results locally.

## Remaining limitations and review gate

- Windows mGBA execution, socket scheduling, physical-input interactions and GUI
  save-path verification remain untested. The v0.2 T7 root cause is still unknown;
  fixed cleanup and better tests are not evidence that live stability now passes.
- If both emulator release APIs fail, the process crashes or emulation stops
  scheduling callbacks, software cannot guarantee release; errors are surfaced and
  the operator must pause/stop the isolated emulator. No wall-clock background
  watchdog or autonomous controller is introduced.
- Basename checks are not an OS filesystem sandbox. Lua cannot portably resolve
  Windows reparse points or atomically reserve files before mGBA opens them.
  There is a check/open race if another local process can alter the directory.
  The trusted, empty, owner-controlled directory and disabled state commands are
  prerequisites. No filesystem security claim is made against hostile local users.
- Loopback has no authentication; any local process can connect. No LAN/public
  listener is allowed. Source/hash checks and bridge self-report cannot attest to
  what code a hostile process actually loaded; the operator must verify the process.
- S3 remains source review plus a regression guard, not a formal proof. The runner
  verifies the reviewed source hash but cannot infer the loaded script hash.
- All-pass covers automated checks only; screenshot visual agreement and the
  active save path still need owner evidence. Do not proceed to Phase 2 until
  review/approval and the intended live T1–T8/S1–S3 gates are complete.
