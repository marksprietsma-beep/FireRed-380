# Test protocol

Run the live battery only after the save-isolation blocker has been resolved. Record the actual result and evidence; do not infer a pass from code inspection.

All transport checks should use the loopback socket at `127.0.0.1:8888`.

## Transport and bridge

| # | Test | Pass condition |
|---|---|---|
| T1 | Ping | `bridge.ping` returns `pong` |
| T2 | Frame counter | Numeric frame counter increases between calls |
| T8 | Multi-command framing | Two commands sent in one write return two correctly ordered replies |

## Observation

| # | Test | Pass condition |
|---|---|---|
| T3 | Memory reads | read8/read16/read32/range return valid values |
| T4 | Screenshot | PNG exists, decodes and is 240×160; visual content matches mGBA |

## Control

| # | Test | Pass condition |
|---|---|---|
| T5 | Discrete press and release | A is pressed during the window and released after it |
| T6 | Clear-all interruption | `bridge.clearAll` releases active keys and cancels queued presses |

## Save protection

| # | Test | Pass condition |
|---|---|---|
| S1 | Save-path isolation | mGBA's active save path is identified and is a separate disposable file approved by the owner |
| S2 | No protected-save mutation | Hash of the protected original remains unchanged before and after; no test action writes to it |
| S3 | No memory-write surface | Bridge source exposes no arbitrary RAM-write command or cheat surface |

Do not proceed with gameplay unless S1–S3 pass. A savestate is not a substitute for protecting the `.sav` file.

## Stability

| # | Test | Pass condition |
|---|---|---|
| T7 | Fresh-connection stability | 30 fresh-connection pings pass with no failures |

## Completion gate

Phase 1 is complete only when T1–T8 and S1–S3 pass on the intended Windows/mGBA setup. The historical report in `workspace/state/battery_report.json` is a pre-fix v0.2 result of 5/8, not a current pass.
