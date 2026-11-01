"""bridge_client.py — minimal TCP client for the FireRed-380 mGBA Lua bridge.

Protocol (matches FireRedBridgeSocketServer_v0.2_fixed.lua and v0.3):
    request : "<cmd>,<a1>,<a2>...<|END|>"   (one command per call)
    reply   : "<payload><|END|>"            (payload starts with "<|ERROR|>" on failure)

Binds to localhost only; the bridge is 127.0.0.1:8888 by design.
No third-party dependencies (stdlib only, Python 3.14).
"""
from __future__ import annotations

import socket
import time

END_MARKER = "<|END|>"
OK_PREFIX = "<|OK|>"
ERR_PREFIX = "<|ERROR|>"


class BridgeError(RuntimeError):
    """Raised when the bridge is unreachable or a call keeps failing."""


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
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay

    # ---------- core ----------
    def call(self, cmd: str, *args: object) -> str:
        """Send one command, return the decoded payload (marker stripped).

        Raises BridgeErrorResponse for <ERROR> payloads, BridgeError for
        transport failures after exhausting retries.
        """
        request = ",".join([cmd, *(str(a) for a in args)]) + END_MARKER
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            sock = None
            try:
                sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
                sock.settimeout(self.timeout)
                sock.sendall(request.encode("latin1"))
                buf = b""
                marker = END_MARKER.encode("latin1")
                while marker not in buf:
                    chunk = sock.recv(4096)
                    if not chunk:
                        raise BridgeError("connection closed before END marker")
                    buf += chunk
                payload = buf.split(marker, 1)[0].decode("latin1", "replace").strip()
                if payload.startswith(ERR_PREFIX):
                    raise BridgeErrorResponse(cmd, payload)
                return payload
            except (BridgeErrorResponse, BridgeError):
                raise
            except OSError as exc:
                last_error = exc
                time.sleep(self.retry_delay)
        raise BridgeError(f"bridge call failed after {self.retries + 1} attempts: {last_error}")

    def call_raw(self, raw_requests: list[str]) -> list[str]:
        """Send multiple framed requests and read back matching replies (B3 test).

        `raw_requests` elements must NOT include the END marker.
        """
        marker = END_MARKER.encode("latin1")
        stream = "".join(r + END_MARKER for r in raw_requests).encode("latin1")
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        try:
            sock.settimeout(self.timeout)
            sock.sendall(stream)
            buf = b""
            replies: list[str] = []
            while len(replies) < len(raw_requests):
                buf += sock.recv(4096)
                while marker in buf:
                    head, buf = buf.split(marker, 1)
                    replies.append(head.decode("latin1", "replace").strip())
                    if len(replies) >= len(raw_requests):
                        break
            return replies
        finally:
            sock.close()

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
