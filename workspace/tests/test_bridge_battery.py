"""test_bridge_battery.py — live test battery against the running mGBA Lua bridge.

Runs the user-ordered checks:
  T1  ping -> pong
  T2  frame counter reads (advancing)
  T3  game memory reads (read-only): read8/16/32 + readRangeHex
  T4  screenshot capture -> PNG 240x160 on disk
  T5  discrete button press (A) with key-state + screenshot evidence
  T6  release / input interruption (keys release, clearAll)
  T7  connection stability across repeated requests (30 fresh conns + B3 multi-command)

Writes a JSON report to workspace/state/battery_report.json and prints PASS/FAIL per check.
Exit code 0 = all pass, 1 = at least one failure.
"""
from __future__ import annotations

import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
SRC = HERE.parent.parent / "src"
sys.path.insert(0, str(SRC))

from bridge_client import BridgeClient, BridgeError, BridgeErrorResponse  # noqa: E402

ROOT = HERE.parent.parent  # .../FireRed-380/workspace
STATE = ROOT / "state"
STATE.mkdir(parents=True, exist_ok=True)

SHOT_A_HOLD = str(STATE / "t5_a_held.png")
SHOT_BASELINE = str(STATE / "t4_baseline.png")
STABILITY_N = 30

results: list[dict] = []


def record(tid: str, name: str, ok: bool, detail: str) -> None:
    results.append({"test": tid, "name": name, "pass": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {tid} {name}: {detail}")


def png_size(path: Path) -> tuple[int, int] | None:
    if not path.exists() or path.stat().st_size < 24:
        return None
    b = path.read_bytes()
    if b[:8] != b"\x89PNG\r\n\x1a\n" or b[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", b[16:24])
    return w, h


def main() -> int:
    c = BridgeClient(timeout=10.0, retries=2)

    # ---- T1 ping ----
    try:
        r = c.ping()
        record("T1", "ping -> pong", r == "pong", f"reply={r!r}")
    except (BridgeError, BridgeErrorResponse) as e:
        record("T1", "ping -> pong", False, str(e))
        finish()
        return 1

    # ---- T2 frame counter ----
    try:
        f1 = c.frame()
        time.sleep(0.35)  # ~20 frames at 60fps
        f2 = c.frame()
        record("T2", "frame counter advancing", f2 > f1, f"f1={f1} f2={f2} delta={f2 - f1}")
    except (BridgeError, BridgeErrorResponse) as e:
        record("T2", "frame counter advancing", False, str(e))

    # ---- T3 memory reads (read-only) ----
    try:
        v8 = c.read8(0x00000000)   # IRQ enable / IME area
        v16 = c.read16(0x3007000)  # VRAM (read-only region)
        v32 = c.read32(0x03007000)
        h = c.read_range_hex(0x03007000, 64)
        ok = 0 <= v8 <= 255 and 0 <= v16 <= 65535 and 0 <= v32 <= 4294967295 and len(h) == 128
        record("T3", "memory reads (8/16/32/range)", ok,
               f"read8(0x0)={v8:#x} read16(0x03007000)={v16:#x} read32={v32:#x} range_hex[{len(h)}]={h[:32]}...")
    except (BridgeError, BridgeErrorResponse) as e:
        record("T3", "memory reads (8/16/32/range)", False, str(e))

    # ---- T4 screenshot ----
    try:
        if Path(SHOT_BASELINE).exists():
            Path(SHOT_BASELINE).unlink()
        r = c.screenshot(SHOT_BASELINE)
        p = Path(SHOT_BASELINE)
        size = png_size(p)
        ok = p.exists() and p.stat().st_size > 1000 and size == (240, 160)
        record("T4", "screenshot capture 240x160", ok,
               f"reply={r!r} bytes={p.stat().st_size if p.exists() else 'MISSING'} dims={size}")
    except (BridgeError, BridgeErrorResponse) as e:
        record("T4", "screenshot capture 240x160", False, str(e))

    # ---- T5 discrete press (A, 120 frames ~2s) + key-state + screenshot mid-hold ----
    try:
        k0 = c.keys()
        c.hold_keys("A", 120)
        time.sleep(0.3)  # inside the 120-frame window (~2s)
        k1 = c.keys()
        if Path(SHOT_A_HOLD).exists():
            Path(SHOT_A_HOLD).unlink()
        r = c.screenshot(SHOT_A_HOLD)
        released_after = False
        time.sleep(2.2)  # let the window expire
        k2 = c.keys()
        released_after = (k2 & 0x1) == 0
        pressed = (k1 & 0x1) == 1
        record("T5", "discrete A press + key state", pressed and released_after,
               f"keys before={k0:#06x} during={k1:#06x} after-window={k2:#06x} shot={r!r} dims={png_size(Path(SHOT_A_HOLD))}")
    except (BridgeError, BridgeErrorResponse) as e:
        record("T5", "discrete A press + key state", False, str(e))

    # ---- T6 release / interruption ----
    try:
        c.hold_keys("A;Down", 300)  # long hold (5s) so we can interrupt it
        time.sleep(0.3)
        c.clear_all()
        time.sleep(0.2)
        k = c.keys()
        record("T6", "release + clearAll interruption", (k & 0x43) == 0,
               f"keys after clearAll during active hold={k:#06x}")
        time.sleep(5.0)  # let the expired window age out cleanly
    except (BridgeError, BridgeErrorResponse) as e:
        record("T6", "release + clearAll interruption", False, str(e))

    # ---- T7 stability: 30 fresh connections ----
    try:
        t0 = time.time()
        fails = 0
        last_err = None
        for i in range(STABILITY_N):
            try:
                if c.ping() != "pong":
                    fails += 1
            except (BridgeError, BridgeErrorResponse) as e:
                fails += 1
                last_err = repr(e)
        wall = time.time() - t0
        detail = f"failures={fails}/{STABILITY_N} wall={wall:.2f}s avg={wall / STABILITY_N * 1000:.0f}ms"
        if last_err:
            detail += f" last_err={last_err}"
        record("T7", f"stability: {STABILITY_N} fresh-connection pings", fails == 0, detail)
    except Exception as e:  # noqa: BLE001
        record("T7", f"stability: {STABILITY_N} fresh-connection pings", False, str(e))

    # ---- B3: two commands in one TCP write -> two in-order replies ----
    try:
        replies = c.call_raw(["bridge.ping", "bridge.frame"])
        ok = len(replies) == 2 and replies[0] == "pong" and replies[1].isdigit()
        record("T8", "B3 multi-command framing", ok, f"replies={replies!r}")
    except Exception as e:  # noqa: BLE001
        record("T8", "B3 multi-command framing", False, str(e))

    return finish()


def finish() -> int:
    report = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "target": "127.0.0.1:8888 (mGBA Lua bridge)",
        "results": results,
        "all_pass": all(r["pass"] for r in results) and len(results) > 0,
    }
    out = STATE / "battery_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    ok = report["all_pass"]
    print(f"\n=== BATTERY {'ALL PASS' if ok else 'HAS FAILURES'} -> {out} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
