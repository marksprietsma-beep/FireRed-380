"""Upstream compatibility adapter; FireRed-380 BridgeClient is the ONLY transport.

Modified from pinned upstream: HTTP fallback, port scanning, persistent/replaying
socket client and unrestricted file/reset operations have been removed.
"""
from __future__ import annotations

import csv
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workspace/src"))
from bridge_client import BRIDGE_VERSION, BridgeClient, BridgeError

_CLIENT = BridgeClient(timeout=10, retries=1)
_ACTION_LOCK = threading.Lock()


def _authorized():
    from .safety import require_authorized
    require_authorized()


def _socket_client():
    return _CLIENT


def mgba_read8(addr):
    _authorized()
    return _CLIENT.read8(addr)


def mgba_read16(addr):
    _authorized()
    return _CLIENT.read16(addr)


def mgba_read32(addr):
    _authorized()
    return _CLIENT.read32(addr)


def mgba_read_range_bytes(addr, length):
    _authorized()
    if not isinstance(length, int) or not 0 <= length <= 1024 * 1024:
        raise ValueError("range length must be 0..1048576")
    return b"".join(bytes.fromhex(_CLIENT.read_range_hex(addr + offset, min(4096, length - offset)))
                    for offset in range(0, length, 4096))


def mgba_read_range(addr, length):
    return list(mgba_read_range_bytes(addr, length))


def mgba_read_ranges_bytes(ranges):
    return [mgba_read_range_bytes(addr, length) for addr, length in ranges]


def mgba_read_ranges(ranges):
    return [list(value) for value in mgba_read_ranges_bytes(ranges)]


def _press(keys, frames):
    from .safety import claim_action
    claim_action()
    with _ACTION_LOCK:
        try:
            start = _CLIENT.frame()
            _CLIENT.hold_keys(keys, frames)  # once only; uncertain outcomes propagate
            deadline = time.monotonic() + 10
            while True:
                frame = _CLIENT.frame()
                if frame < start:
                    raise BridgeError("frame reset during action")
                if frame > start + frames + 2 and _CLIENT.keys() == 0:
                    return {"ok": True, "endpoint": "hardened-socket", "frames": frames}
                if time.monotonic() > deadline:
                    raise BridgeError("input release deadline exceeded")
                time.sleep(0.01)
        finally:
            _CLIENT.clear_all()
            if _CLIENT.keys() != 0:
                raise BridgeError("input cleanup failed; pause emulator")


def mgba_press_buttons(buttons):
    return _press(buttons, 12)


def mgba_hold_button(button, frames):
    return _press(button, frames)


def mgba_control(command):
    name = command.strip().lower()
    facing = name.startswith("face_")
    if facing:
        name = name[5:]
    if name not in {"a", "b", "l", "r", "start", "select", "up", "down", "left", "right"}:
        raise ValueError("unsupported control")
    # The upstream API observes position/lock transitions after this bounded pulse.
    # This does not claim upstream Lua's exact smart-one-tile movement semantics.
    _press(name, 1 if facing else (8 if name in {"up", "down", "left", "right"} else 12))
    return "control.ok"


def _safe_file(filepath, suffix):
    _authorized()
    root = Path(_CLIENT.call("bridge.outputDir")).resolve()
    path = Path(filepath)
    if path.is_absolute():
        if path.parent.resolve() != root:
            raise ValueError("file must be inside configured bridge output directory")
        path = Path(path.name)
    if path.name != str(path) or path.suffix != suffix:
        raise ValueError("sandbox basename and expected extension required")
    return path.name


def mgba_screenshot(filepath):
    name = _safe_file(filepath, ".png")
    return {"ok": True, "result": _CLIENT.screenshot(name), "endpoint": "hardened-socket"}


def mgba_save_state_file(filepath):
    # No upstream automatic backup generation/pruning. Explicit recovery only.
    if os.environ.get("FIRERED_ENABLE_RECOVERY_STATES") != "1":
        raise PermissionError("recovery states disabled")
    name = _safe_file(filepath, ".mgbs")
    return {"ok": True, "result": _CLIENT.save_state_file(name)}


def mgba_reset():
    raise PermissionError("reset excluded: explicit operator intervention required")


def _socket_request(message):
    """Compatibility for upstream control and batched reads, without a second socket."""
    parts = next(csv.reader([message]))
    cmd, args = parts[0], parts[1:]
    if cmd == "bridge.controlInit":
        return "controlInit.ok"  # no Lua pointer configuration or memory writes
    if cmd == "bridge.control":
        return mgba_control(args[0])
    if cmd == "bridge.controlStatus":
        _authorized()
        return "queue=0,active=" + ("none" if _CLIENT.keys() == 0 else "hold")
    if cmd in {"bridge.readRangesHex", "bridge.readRanges"}:
        raw = message.split(",", 1)[1].strip("[]")
        values = raw.split(",")
        pairs = [(int(values[i], 0), int(values[i + 1])) for i in range(0, len(values), 2)]
        return "|".join(value.hex() for value in mgba_read_ranges_bytes(pairs))
    raise ValueError("unsupported legacy command: " + cmd)
