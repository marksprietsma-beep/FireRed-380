"""Explicit, narrowly scoped owner authorisation. Never probes files on import."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path, PureWindowsPath

ROM_PATH = PureWindowsPath(r"C:\Emu\1636 - Pokemon Fire Red (U)(Squirrels).gba")
SAVE_PATH = ROM_PATH.with_suffix(".sav")
ROM_MD5 = "e26ee0d44e809351c8ce2d73c7400cdd"
ROM_SHA256 = "3d0c79f1627022e18765766f6cb5ea067f6b5bf7dca115552189ad65a5c3a8ac"


def verify_owner_rom(manifest: dict, *, opt_in: bool = False) -> dict:
    if not opt_in or manifest.get("owner_authorized_save_modification") is not True:
        raise PermissionError("explicit owner-authorized save modification opt-in required")
    if sys.platform != "win32":
        raise ValueError("owner-authorized testing requires Windows")
    # Check exact approved targets BEFORE any file operation. No other ROM/save is probed.
    if (PureWindowsPath(manifest.get("rom_path", "")) != ROM_PATH
            or PureWindowsPath(manifest.get("active_save", "")) != SAVE_PATH):
        raise ValueError("only the exact owner-approved Squirrels ROM and adjacent save are allowed")
    if manifest.get("active_rom_path_verified_in_mgba") is not True:
        raise ValueError("operator must verify the actual loaded ROM path")
    if manifest.get("active_save_path_verified_in_mgba") is not True:
        raise ValueError("operator must verify the active save is the approved adjacent .sav")
    rom = Path(str(ROM_PATH))
    for part in (rom, *rom.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("ROM path must not use a symlink or reparse point")
    md5, sha = hashlib.md5(usedforsecurity=False), hashlib.sha256()
    with rom.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            md5.update(chunk); sha.update(chunk)
    if md5.hexdigest() != ROM_MD5 or sha.hexdigest() != ROM_SHA256:
        raise ValueError("approved ROM MD5/SHA-256 mismatch")
    return {"mode": "owner-authorized", "S1": "OWNER-WAIVED", "S2": "OWNER-WAIVED",
            "rom_md5": md5.hexdigest(), "rom_sha256": sha.hexdigest()}
