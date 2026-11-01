"""Session gate shared by all integrated readers/actions; protected by default."""
import importlib.util
import json
import os
import threading
from pathlib import Path

_lock = threading.RLock()
_session = None
_paused = True
_remaining = 0


def battery_module():
    path = Path(__file__).resolve().parents[1] / "workspace/tests/test_bridge_battery.py"
    spec = importlib.util.spec_from_file_location("firered_live_battery", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_authorized():
    global _session
    with _lock:
        if _session is None:
            filename = os.environ.get("FIRERED_TEST_MANIFEST")
            if not filename:
                raise PermissionError("no approved test manifest; emulator access is locked")
            manifest = json.loads(Path(filename).read_text(encoding="utf-8"))
            b = battery_module()
            owner_mode = os.environ.get("FIRERED_OWNER_AUTHORIZED_TESTING") == "1"
            if owner_mode:
                output, protected = b.verify_owner_safety(manifest, opt_in=True)
            else:
                output, protected = b.verify_safety(manifest)
            b.verify_listener(manifest)
            from .mgba_client import _CLIENT
            if _CLIENT.version() != "0.3.1" or Path(_CLIENT.call("bridge.outputDir")).resolve() != output:
                raise PermissionError("loaded bridge version/output configuration mismatch")
            _session = {"mode": "owner-authorized" if owner_mode else "protected",
                        "output": output, "protected": protected, "battery": b}
        _session["battery"].verify_hashes(_session["protected"])
        return _session


def require_actions():
    require_authorized()
    if _paused:
        raise PermissionError("actions paused; explicitly resume a bounded supervised sequence")


def pause():
    global _paused, _remaining
    _paused, _remaining = True, 0
    if _session is not None:
        from .mgba_client import _CLIENT
        _CLIENT.clear_all()
        if _CLIENT.keys():
            raise RuntimeError("keys remain pressed")


def resume():
    global _paused, _remaining
    require_authorized()
    _paused, _remaining = False, 10


def status():
    return {"authorized": _session is not None, "paused": _paused,
            "remaining_actions": _remaining, "mode": _session["mode"] if _session else "protected"}


def claim_action():
    global _remaining, _paused
    with _lock:
        require_actions()
        if _remaining <= 0:
            _paused = True
            raise PermissionError("ten-action budget exhausted; operator must approve another sequence")
        _remaining -= 1
