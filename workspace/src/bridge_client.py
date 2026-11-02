"""bridge_client.py — minimal TCP client for the FireRed-380 mGBA Lua bridge.

Protocol (matches FireRedBridgeSocketServer_v0.2_fixed.lua and v0.3):
    request : "<cmd>,<a1>,<a2>...<|END|>"   (one command per call)
    reply   : "<payload><|END|>"            (payload starts with "<|ERROR|>" on failure)

Binds to localhost only; the bridge is 127.0.0.1:8888 by design.
No third-party dependencies (Python 3.10+). UTF-8, quoted CSV arguments.
"""
from __future__ import annotations

import csv
import io
import math
import re
import socket
import time

END_MARKER = "<|END|>"
OK_PREFIX = "<|OK|>"
ERR_PREFIX = "<|ERROR|>"
BRIDGE_VERSION = "0.3.1"
MAX_HOLD_FRAMES = 300
MAX_MESSAGE_BYTES = 131072
READ_ONLY = frozenset({
    "bridge.ping", "bridge.version", "bridge.info", "bridge.outputDir",
    "bridge.frame", "bridge.read8", "bridge.read16", "bridge.read32",
    "bridge.readRangeHex", "bridge.keys",
})


class BridgeError(RuntimeError):
    """Raised when the bridge is unreachable or a call keeps failing."""


class BridgeUncertainError(BridgeError):
    """A mutating request may have executed. Observe state; do not replay it."""


class BridgeErrorResponse(BridgeError):
    """The bridge answered, but the payload was an <ERROR> reply."""

    def __init__(self, cmd: str, payload: str):
        self.cmd = cmd
        self.payload = payload
        super().__init__(f"{cmd} -> {payload}")


class BridgeClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8888,
        timeout: float = 10.0,
        retries: int = 2,
        retry_delay: float = 0.4,
    ) -> None:
        if host != "127.0.0.1":
            raise ValueError("bridge host must be 127.0.0.1")
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError("invalid port")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
            raise ValueError("retries must be a nonnegative integer")
        if not math.isfinite(retry_delay) or retry_delay < 0:
            raise ValueError("retry_delay must be finite and nonnegative")
        self.host, self.port = host, port
        self.timeout, self.retries, self.retry_delay = timeout, retries, retry_delay

    @staticmethod
    def serialize(cmd: str, *args: object) -> str:
        """CSV quoting preserves commas, apostrophes, quotes and path spaces.

        Markers/control characters are rejected rather than escaped: the outer
        framing layer processes markers before parsing CSV. Quotes are doubled.
        """
        if not re.fullmatch(r"bridge\.[A-Za-z][A-Za-z0-9]*", cmd):
            raise ValueError("invalid command")
        fields = [cmd, *(str(arg) for arg in args)]
        if any(END_MARKER in value or any(ord(c) < 32 or ord(c) == 127 for c in value)
               for value in fields):
            raise ValueError("framing markers and control characters are forbidden")
        out = io.StringIO()
        csv.writer(out, lineterminator="", quoting=csv.QUOTE_ALL).writerow(fields[1:])
        # Keep the command unquoted for compatibility with the existing parser.
        return cmd + ("," + out.getvalue() if args else "")

    def _exchange(self, requests: list[str], mutating: bool) -> list[str]:
        stream = (END_MARKER.join(requests) + END_MARKER).encode("utf-8")
        if len(stream) > MAX_MESSAGE_BYTES:
            raise ValueError("request exceeds message limit")
        deadline = time.monotonic() + self.timeout
        sock = None
        sending = False
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            def remaining() -> float:
                value = deadline - time.monotonic()
                if value <= 0:
                    raise TimeoutError("total request deadline exceeded")
                return value
            sock.settimeout(remaining())
            sending = True  # sendall may fail after writing some/all bytes
            sock.sendall(stream)
            buf = b""
            received = 0
            replies = []
            marker = END_MARKER.encode("ascii")
            while len(replies) < len(requests):
                sock.settimeout(remaining())
                chunk = sock.recv(4096)
                if not chunk:
                    raise BridgeError("connection closed before all replies arrived")
                received += len(chunk)
                if received > MAX_MESSAGE_BYTES:
                    raise BridgeError("response exceeds message limit")
                buf += chunk
                while marker in buf:
                    payload, buf = buf.split(marker, 1)
                    replies.append(payload.decode("utf-8", "strict").strip())
                if len(replies) > len(requests) or (len(replies) == len(requests) and buf):
                    raise BridgeError("unexpected trailing response data")
            return replies
        except (OSError, UnicodeError, BridgeError) as exc:
            if mutating and sending:
                raise BridgeUncertainError(
                    "request may have executed; automatic replay disabled: " + str(exc)
                ) from exc
            raise BridgeError(str(exc)) from exc
        finally:
            if sock is not None:
                sock.close()

    def call(self, cmd: str, *args: object) -> str:
        request = self.serialize(cmd, *args)
        read_only = cmd in READ_ONLY
        for attempt in range((self.retries if read_only else 0) + 1):
            try:
                payload = self._exchange([request], mutating=not read_only)[0]
            except BridgeUncertainError:
                raise
            except BridgeError:
                if not read_only or attempt == self.retries:
                    raise
                time.sleep(self.retry_delay)
                continue
            if payload.startswith(ERR_PREFIX):
                raise BridgeErrorResponse(cmd, payload)
            return payload
        raise AssertionError("unreachable")

    def call_raw(self, raw_requests: list[str]) -> list[str]:
        """Send already serialized commands once; no batch is ever replayed.

        Use serialize() to construct arguments. Raw requests must exclude the
        framing marker. Per-command error replies are returned in order so a
        caller can inspect the complete batch (unlike call(), which raises).
        """
        if not raw_requests:
            return []
        commands = []
        for request in raw_requests:
            if not isinstance(request, str) or END_MARKER in request or any(
                ord(c) < 32 or ord(c) == 127 for c in request
            ):
                raise ValueError("invalid raw request")
            cmd = request.split(",", 1)[0].split(" ", 1)[0]
            if not re.fullmatch(r"bridge\.[A-Za-z][A-Za-z0-9]*", cmd):
                raise ValueError("invalid raw command")
            commands.append(cmd)
        return self._exchange(raw_requests, mutating=any(c not in READ_ONLY for c in commands))

    # ---------- named commands ----------
    def ping(self) -> str:
        r = self.call("bridge.ping")
        if r != "pong":
            raise BridgeErrorResponse("bridge.ping", r)
        return r

    def frame(self) -> int:
        return int(self.call("bridge.frame"))

    def read8(self, addr: int) -> int:
        return int(self.call("bridge.read8", hex(addr)))

    def read16(self, addr: int) -> int:
        return int(self.call("bridge.read16", hex(addr)))

    def read32(self, addr: int) -> int:
        return int(self.call("bridge.read32", hex(addr)))

    def read_range_hex(self, addr: int, length: int) -> str:
        h = self.call("bridge.readRangeHex", hex(addr), length)
        if len(h) != length * 2:
            raise BridgeError(f"readRangeHex: expected {length * 2} hex chars, got {len(h)}")
        return h

    def keys(self) -> int:
        r = self.call("bridge.keys")
        if r == "n/a":
            raise BridgeError("bridge.keys: emu.getKeys not available in this mGBA build")
        return int(r, 16)

    def hold_keys(self, keys: str | list[str], frames: int | None = None) -> str:
        """Discrete press. `keys` like "A" or "Up;Down". frames optional (default 12 in bridge)."""
        if frames is not None and (isinstance(frames, bool) or not isinstance(frames, int)
                                   or not 1 <= frames <= MAX_HOLD_FRAMES):
            raise ValueError(f"frames must be an integer in 1..{MAX_HOLD_FRAMES}")
        spec = keys if isinstance(keys, str) else ";".join(keys)
        if frames is None:
            return self.call("bridge.holdKeys", spec)
        return self.call("bridge.holdKeys", spec, frames)

    def clear_all(self) -> str:
        return self.call("bridge.clearAll")

    def screenshot(self, path: str) -> str:
        return self.call("bridge.screenshot", path)

    def save_state_file(self, path: str) -> str:
        return self.call("bridge.saveStateFile", path)

    def version(self) -> str:
        return self.call("bridge.version")

    def info(self) -> str:
        return self.call("bridge.info")

    def load_state_file(self, path: str) -> str:
        return self.call("bridge.loadStateFile", path)

    def shutdown(self) -> str:
        return self.call("bridge.shutdown")
