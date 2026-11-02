"""Opt-in Windows/mGBA live battery. Never run through test discovery.

Requires an owner-reviewed isolation manifest; see BRIDGE_HARDENING.md.
Importing this module has no network, filesystem-write or emulator side effects.
Historical workspace/state/battery_report.json is never an output destination.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from bridge_client import BRIDGE_VERSION, BridgeClient, BridgeError  # noqa: E402

ALL_KEYS = 0x3FF
BRIDGE = SRC / "FireRedBridgeSocketServer_v0.3.lua"


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        digest = hashlib.sha256()
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def plain_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("safety paths must be absolute")
    # On Windows, reject junctions/reparse points as well as symlinks.
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("reparse point/symlink in safety path")
    return path.resolve(strict=True)


def directories_overlap(first: Path, second: Path) -> bool:
    """Resolved directories overlap if equal or either contains the other."""
    return first.is_relative_to(second) or second.is_relative_to(first)


def verify_safety(manifest: dict) -> tuple[Path, dict[Path, str]]:
    if sys.platform != "win32":
        raise ValueError("live battery requires the intended Windows/mGBA setup")
    if manifest.get("owner_approved_isolation") is not True:
        raise ValueError("owner-approved isolation attestation required")
    if manifest.get("active_save_path_verified_in_mgba") is not True:
        raise ValueError("operator must verify the actual active save path in mGBA")
    if manifest.get("host") != "127.0.0.1" or manifest.get("port") != 8888:
        raise ValueError("expected endpoint is 127.0.0.1:8888")
    if manifest.get("bridge_version") != BRIDGE_VERSION or manifest.get("bridge_sha256") != sha256(BRIDGE):
        raise ValueError("reviewed bridge version/hash mismatch")
    source = BRIDGE.read_text(encoding="utf-8")
    # A supplementary regression guard; source review remains the authority for S3.
    if any(token in source for token in ("emu:write", "emu.memory", "emu:loadROM")):
        raise ValueError("unexpected memory-write/ROM surface; repeat S3 review")
    output = plain_path(manifest["output_dir"])
    active = plain_path(manifest["active_save"])
    isolated = plain_path(manifest["disposable_save_dir"])
    checkout = Path(__file__).resolve().parents[2]
    if directories_overlap(output, checkout):
        raise ValueError("output directory must not overlap the checkout")
    if directories_overlap(isolated, checkout):
        raise ValueError("disposable save directory must not overlap the checkout")
    if directories_overlap(output, isolated):
        raise ValueError("output and disposable save directories must not overlap")
    if not output.is_dir() or any(output.iterdir()):
        raise ValueError("output must be a new empty directory outside the checkout")
    if not isolated.is_dir() or not active.is_file() or active.suffix.lower() != ".sav" or active.parent != isolated:
        raise ValueError("active save must be an existing disposable .sav in its isolated directory")
    if not manifest.get("protected_files"):
        raise ValueError("protected original and backup hashes required")
    protected = {}
    for item in manifest["protected_files"]:
        path = plain_path(item["path"])
        if (not path.is_file() or path == active or os.path.samefile(path, active)
                or directories_overlap(isolated, path.parent)
                or directories_overlap(output, path.parent)):
            raise ValueError("protected files must be separate from disposable save and output directories")
        digest = sha256(path)
        if digest != item["sha256"]:
            raise ValueError("protected file hash mismatch before testing")
        protected[path] = digest
    return output, protected


def verify_owner_safety(manifest: dict, *, opt_in: bool = False):
    from owner_testing import verify_owner_rom
    verify_owner_rom(manifest, opt_in=opt_in)
    if manifest.get("host") != "127.0.0.1" or manifest.get("port") != 8888:
        raise ValueError("expected endpoint is 127.0.0.1:8888")
    if manifest.get("bridge_version") != BRIDGE_VERSION or manifest.get("bridge_sha256") != sha256(BRIDGE):
        raise ValueError("reviewed bridge version/hash mismatch")
    output = plain_path(manifest["output_dir"])
    checkout = Path(__file__).resolve().parents[2]
    rom_dir = Path(manifest["rom_path"]).parent.resolve()
    if (not output.is_dir() or any(output.iterdir()) or directories_overlap(output, checkout)
            or directories_overlap(output, rom_dir)):
        raise ValueError("owner-mode output must be new, empty and separate from ROM/save and checkout")
    return output, {}  # no save-preservation checks in this explicitly opted-in mode


def verify_listener(manifest: dict) -> None:
    """Check the OS listener and owning executable, not just bridge self-report."""
    pid = manifest.get("mgba_pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise ValueError("expected mGBA PID required")
    expected_executable = plain_path(manifest["mgba_executable"])
    command = (
        "$ErrorActionPreference='Stop'; "
        "$listeners=@(Get-NetTCPConnection -LocalPort 8888 -State Listen); "
        "$listeners | ForEach-Object { "
        "[pscustomobject]@{Address=$_.LocalAddress;Port=$_.LocalPort;"
        "Pid=$_.OwningProcess;Executable=(Get-Process -Id $_.OwningProcess).Path} "
        "} | ConvertTo-Json -Compress"
    )
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, check=True, timeout=15)
    records = json.loads(result.stdout)
    if not isinstance(records, list):
        records = [records]
    if (len(records) != 1 or records[0]["Address"] != "127.0.0.1"
            or records[0]["Port"] != 8888 or records[0]["Pid"] != pid
            or plain_path(records[0]["Executable"]) != expected_executable):
        raise ValueError("port 8888 must have exactly the expected loopback mGBA listener")


def wait_frames(c: BridgeClient, target: int, timeout: float = 15.0) -> int:
    deadline = time.monotonic() + timeout
    previous = c.frame()
    while previous < target:
        if time.monotonic() >= deadline:
            raise BridgeError("emulator did not advance to target frame")
        time.sleep(0.01)
        frame = c.frame()
        if frame < previous:
            raise BridgeError("frame counter reset during test")
        previous = frame
    return previous


def wait_keys(c: BridgeClient, mask: int, timeout: float = 5.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if c.keys() & mask == mask:
            return c.frame()
        time.sleep(0.01)
    raise BridgeError("expected keys were not observed pressed")


def released(c: BridgeClient) -> None:
    c.clear_all()
    if c.keys() & ALL_KEYS:
        raise BridgeError("keys remain pressed after clearAll")


def png_size(path: Path) -> tuple[int, int]:
    """Check chunk CRCs and decompress a standard, noninterlaced RGB/RGBA PNG."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("invalid PNG signature")
    offset, pixels, header, ended = 8, bytearray(), None, False
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise ValueError("PNG CRC mismatch")
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            pixels.extend(payload)
        elif kind == b"IEND":
            ended = True
            break
        offset += length + 12
    if not ended or header is None:
        raise ValueError("incomplete PNG")
    w, h, depth, color, compression, filtering, interlace = header
    if (w, h) != (240, 160) or depth != 8 or color not in (2, 6) or any((compression, filtering, interlace)):
        raise ValueError("unsupported PNG shape/encoding")
    raw = zlib.decompress(pixels)
    stride = 1 + w * (3 if color == 2 else 4)
    if len(raw) != h * stride or any(raw[i] > 4 for i in range(0, len(raw), stride)):
        raise ValueError("invalid PNG scanlines")
    return w, h


def t5(c: BridgeClient) -> str:
    try:
        released(c)
        c.hold_keys("A", 120)
        pressed_frame = wait_keys(c, 0x1)
        end = wait_frames(c, pressed_frame + 121)
        if c.keys() & 0x1:
            raise BridgeError("A still pressed after 120 actual frames")
        return f"A observed at frame {pressed_frame}; released at {end}"
    finally:
        released(c)


def t6(c: BridgeClient) -> str:
    try:
        released(c)
        c.hold_keys("A;Down", 300)
        pressed_frame = wait_keys(c, 0x81)
        released(c)
        wait_frames(c, pressed_frame + 301)
        if c.keys() & ALL_KEYS:
            raise BridgeError("keys reappeared after cancelled hold expired")
        return "A and Down observed; all ten keys released; cancelled queue stayed clear"
    finally:
        released(c)


def run_checks(c: BridgeClient, output: Path, protected: dict[Path, str], *, owner_authorized=False) -> dict:
    results = []
    def check(tid, fn):
        try:
            detail = fn()
            results.append({"test": tid, "pass": True, "detail": str(detail)})
        except Exception as exc:
            results.append({"test": tid, "pass": False, "detail": str(exc)})
        print(f"{tid}: {'PASS' if results[-1]['pass'] else 'FAIL'}")
        return results[-1]["pass"]

    def preflight():
        if c.host != "127.0.0.1" or c.port != 8888 or c.retries != 0:
            raise ValueError("incorrect live client configuration")
        if c.version() != BRIDGE_VERSION:
            raise BridgeError("bridge version mismatch")
        expected = (f"version={BRIDGE_VERSION};host=127.0.0.1;port=8888;"
                    "callbacks=ready;maxHold=300;pathPolicy=basename")
        if c.info() != expected or Path(c.call("bridge.outputDir")).resolve() != output:
            raise BridgeError("bridge endpoint/callback/path policy mismatch")
        if c.keys() & ALL_KEYS:
            raise BridgeError("release all keys manually before testing")
        return "version, endpoint, callback readiness and output policy match"

    def ping():
        if c.ping() != "pong":
            raise BridgeError("unexpected ping response")
        return "pong"

    def memory():
        values = (c.read8(0), c.read16(0x03007000), c.read32(0x03007000))
        if not all(0 <= value <= limit for value, limit in zip(values, (255, 65535, 4294967295))):
            raise BridgeError("out-of-range memory response")
        raw = c.read_range_hex(0x03007000, 64)
        if len(bytes.fromhex(raw)) != 64:
            raise BridgeError("invalid hex range")
        return "read8/16/32/range valid (not a verified game-state field)"

    def screenshot():
        name = "battery-" + uuid.uuid4().hex + ".png"
        c.screenshot(name)
        return str(png_size(output / name)) + "; visual comparison remains manual"

    def stability():
        # c.retries == 0 is enforced before any test; every ping uses one socket.
        failures = []
        for i in range(30):
            try:
                ping()
            except Exception as exc:
                failures.append(f"{i + 1}: {exc}")
        if failures:
            raise BridgeError("; ".join(failures))
        return "30/30 first-attempt fresh-connection pings"

    def framing():
        replies = c.call_raw(["bridge.ping", "bridge.frame", "bridge.unknown", "bridge.ping"])
        if (len(replies) != 4 or replies[0] != "pong" or not replies[1].isdigit()
                or not replies[2].startswith("<|ERROR|>") or replies[3] != "pong"):
            raise BridgeError(f"bad ordered batch replies: {replies!r}")
        return "four ordered replies, including error and subsequent successful reply"

    surface_ok = check("S3", lambda: verify_read_only_surface())
    preflight_ok = check("PREFLIGHT", preflight)
    if preflight_ok and surface_ok:
        try:
            # Do not continue to inputs if observational/transport checks fail.
            observations_ok = all([check("T1", ping),
                check("T2", lambda: wait_frames(c, c.frame() + 20)),
                check("T3", memory), check("T4", screenshot)])
            if observations_ok:
                if owner_authorized or check("S2_BEFORE_INPUT", lambda: verify_hashes(protected)):
                    if check("T5", lambda: t5(c)):
                        if owner_authorized or check("S2_AFTER_T5", lambda: verify_hashes(protected)):
                            check("T6", lambda: t6(c))
            check("T7", stability)
            check("T8", framing)
        finally:
            check("KEYS_RELEASED", lambda: released(c) or "all ten keys verified clear")
    if owner_authorized:
        results.extend({"test": tid, "status": "OWNER-WAIVED", "pass": None,
                        "detail": "owner explicitly waived this check"} for tid in ("S1", "S2"))
    else:
        check("S2", lambda: verify_hashes(protected))
    required = {"S3", "PREFLIGHT", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "KEYS_RELEASED", "S2", "S2_BEFORE_INPUT", "S2_AFTER_T5"}
    if owner_authorized:
        required.discard("S2_BEFORE_INPUT")
        required.discard("S2_AFTER_T5")
        required.add("S1")
        required.add("S2")
    return {"time": datetime.now(timezone.utc).isoformat(), "bridge_version": BRIDGE_VERSION,
            "target": "127.0.0.1:8888", "results": results,
            "all_pass": {r["test"] for r in results} == required and all(r["pass"] is True or r.get("status") == "OWNER-WAIVED" for r in results),
            "mode": "owner-authorized" if owner_authorized else "protected",
            "S1": "OWNER-WAIVED" if owner_authorized else "operator-attested active save path plus filesystem separation checks; not discovered from mGBA",
            "S2": "OWNER-WAIVED" if owner_authorized else "see S2 result",
            "waived_checks": ["S1", "S2"] if owner_authorized else [],
            "S3": "reviewed source hash plus static surface guard; no live memory-write test",
            "manual_remaining": ["visually compare screenshot with mGBA", "verify actual active .sav destination"]}


def verify_read_only_surface():
    source = BRIDGE.read_text(encoding="utf-8")
    if any(token in source for token in ("emu:write", "emu.memory", "emu:loadROM", "emu:loadSave")):
        raise ValueError("S3 failed: unexpected write/cheat surface")
    return "reviewed hardened Lua dispatch has no arbitrary RAM-write or cheat command"


def verify_hashes(protected: dict[Path, str]) -> str:
    for path, digest in protected.items():
        if sha256(path) != digest:
            raise ValueError("protected save/backup changed: STOP")
    return "all protected hashes unchanged"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safety-json", required=True, type=Path)
    parser.add_argument("--owner-authorized-save-modification", action="store_true")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.safety_json.read_text(encoding="utf-8"))
        if args.owner_authorized_save_modification:
            output, protected = verify_owner_safety(manifest, opt_in=True)
        else:
            output, protected = verify_safety(manifest)
        verify_listener(manifest)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))  # no sockets opened on failed safety validation
    report = run_checks(BridgeClient(retries=0), output, protected, owner_authorized=args.owner_authorized_save_modification)
    path = output / ("battery-" + uuid.uuid4().hex + ".json")
    with path.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"New report: {path}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
