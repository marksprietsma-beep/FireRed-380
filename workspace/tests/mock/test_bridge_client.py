import importlib.util
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import bridge_client as bc


def load_battery():
    spec = importlib.util.spec_from_file_location("battery", ROOT / "tests/test_bridge_battery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClientTests(unittest.TestCase):
    def exchange(self, chunks, action=lambda c: c.ping(), **kwargs):
        sock = Mock()
        sock.recv.side_effect = chunks
        with patch.object(bc.socket, "create_connection", return_value=sock) as connect:
            try:
                result = action(bc.BridgeClient(retries=0, **kwargs))
                return result, sock, connect
            finally:
                sock.close.assert_called_once()

    def test_fragmented_ping(self):
        reply, _, _ = self.exchange([b"po", b"ng<|EN", b"D|>"])
        self.assertEqual(reply, "pong")

    def test_batch_order_error_and_partial_marker(self):
        requests = ["bridge.ping", "bridge.frame", "bridge.unknown"]
        replies, _, _ = self.exchange([b"pong<|END|>12<|EN", b"D|><|ERROR|> unknown<|END|>"],
                                     lambda c: c.call_raw(requests))
        self.assertEqual(replies, ["pong", "12", "<|ERROR|> unknown"])

    def test_eof_single(self):
        with self.assertRaises(bc.BridgeError):
            self.exchange([b"po", b""])

    def test_eof_batch(self):
        with self.assertRaises(bc.BridgeError):
            self.exchange([b"pong<|END|>", b""], lambda c: c.call_raw(["bridge.ping", "bridge.frame"]))

    def test_batch_timeout_normalized(self):
        with self.assertRaises(bc.BridgeError):
            self.exchange([TimeoutError()], lambda c: c.call_raw(["bridge.ping"]))

    def test_trickle_has_total_deadline(self):
        sock = Mock()
        sock.recv.return_value = b"x"
        with patch.object(bc.socket, "create_connection", return_value=sock), patch.object(
                bc.time, "monotonic", side_effect=[0, 0.1, 0.2, 0.9, 1.1]):
            with self.assertRaises(bc.BridgeError):
                bc.BridgeClient(timeout=1, retries=0).ping()
        self.assertEqual(sock.recv.call_count, 2)
        sock.close.assert_called_once()

    def test_oversized_response(self):
        with patch.object(bc, "MAX_MESSAGE_BYTES", 64):
            with self.assertRaises(bc.BridgeError):
                self.exchange([b"x" * 65])

    def test_extra_response_rejected(self):
        with self.assertRaises(bc.BridgeError):
            self.exchange([b"pong<|END|>extra<|END|>"])

    def test_error_response_not_retried(self):
        sock = Mock(); sock.recv.return_value = b"<|ERROR|> fail<|END|>"
        with patch.object(bc.socket, "create_connection", return_value=sock) as connect:
            with self.assertRaises(bc.BridgeErrorResponse):
                bc.BridgeClient(retries=4).call("bridge.read8", 0)
        self.assertEqual(connect.call_count, 1)
        sock.close.assert_called_once()

    def test_readonly_retries(self):
        failed, success = Mock(), Mock()
        failed.recv.return_value = b""
        success.recv.return_value = b"pong<|END|>"
        with patch.object(bc.socket, "create_connection", side_effect=[failed, success]) as connect:
            self.assertEqual(bc.BridgeClient(retries=1, retry_delay=0).ping(), "pong")
        self.assertEqual(connect.call_count, 2)
        failed.close.assert_called_once(); success.close.assert_called_once()

    def test_action_never_repeated_after_uncertain_response(self):
        for failure in (b"", TimeoutError(), ConnectionResetError()):
            with self.subTest(failure=failure):
                sock = Mock(); sock.recv.side_effect = [failure]
                with patch.object(bc.socket, "create_connection", return_value=sock) as connect:
                    with self.assertRaises(bc.BridgeUncertainError):
                        bc.BridgeClient(retries=5).hold_keys("A", 120)
                self.assertEqual(connect.call_count, 1)
                sock.sendall.assert_called_once(); sock.close.assert_called_once()

    def test_partial_send_action_not_repeated(self):
        sock = Mock(); sock.sendall.side_effect = TimeoutError()
        with patch.object(bc.socket, "create_connection", return_value=sock) as connect:
            with self.assertRaises(bc.BridgeUncertainError):
                bc.BridgeClient(retries=5).hold_keys("A", 120)
        self.assertEqual(connect.call_count, 1)
        sock.close.assert_called_once()

    def test_mutating_batch_not_replayed(self):
        with self.assertRaises(bc.BridgeUncertainError):
            self.exchange([b"pong<|END|>", b""], lambda c: c.call_raw(["bridge.ping", "bridge.holdKeys,A,12"]))

    def test_connect_failure_normalized_no_mutating_retry(self):
        with patch.object(bc.socket, "create_connection", side_effect=ConnectionRefusedError()) as connect:
            with self.assertRaises(bc.BridgeError) as error:
                bc.BridgeClient(retries=4).clear_all()
            self.assertNotIsInstance(error.exception, bc.BridgeUncertainError)
        self.assertEqual(connect.call_count, 1)

    def test_empty_batch_no_connection(self):
        with patch.object(bc.socket, "create_connection") as connect:
            self.assertEqual(bc.BridgeClient().call_raw([]), [])
            connect.assert_not_called()

    def test_serialization(self):
        self.assertEqual(bc.BridgeClient.serialize("bridge.screenshot", 'capture, O\'Brien "photo".png'),
                         'bridge.screenshot,"capture, O\'Brien ""photo"".png"')
        self.assertEqual(bc.BridgeClient.serialize("bridge.holdKeys", "A;Down", 12),
                         'bridge.holdKeys,"A;Down","12"')

    def test_marker_control_injection_rejected(self):
        for value in ("a<|END|>bridge.shutdown", "x\n", "a\x00", "b\r", "x\x7f"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bc.BridgeClient().screenshot(value)
        with self.assertRaises(ValueError):
            bc.BridgeClient().call_raw(["bridge.ping<|END|>"])

    def test_invalid_duration_not_sent(self):
        with patch.object(bc.socket, "create_connection") as connect:
            for value in (True, False, 0, -1, 1.5, 301, "12"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    bc.BridgeClient().hold_keys("A", value)
            connect.assert_not_called()

    def test_loopback_and_config_validation(self):
        for kwargs in ({"host": "0.0.0.0"}, {"port": 0}, {"timeout": float("nan")},
                       {"timeout": 0}, {"retries": -1}, {"retry_delay": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                bc.BridgeClient(**kwargs)


class BatteryTests(unittest.TestCase):
    def setUp(self):
        self.b = load_battery()

    def test_import_has_no_writes_or_network(self):
        with patch.object(Path, "mkdir") as mkdir, patch.object(bc.socket, "create_connection") as connect:
            load_battery()
        mkdir.assert_not_called(); connect.assert_not_called()

    def test_t5_release_failure_still_cleans_up(self):
        c = Mock(); c.keys.side_effect = [0, 1, 0]
        with patch.object(self.b, "wait_keys", return_value=10), patch.object(self.b, "wait_frames", return_value=131):
            with self.assertRaises(bc.BridgeError):
                self.b.t5(c)
        self.assertEqual(c.clear_all.call_count, 2)

    def test_t5_waits_for_actual_frames(self):
        c = Mock(); c.keys.return_value = 0
        with patch.object(self.b, "wait_keys", return_value=50), patch.object(self.b, "wait_frames", return_value=171) as wait:
            self.b.t5(c)
        wait.assert_called_once_with(c, 171)
        self.assertEqual(c.clear_all.call_count, 2)

    def test_t6_down_stuck_fails_and_cleans_up(self):
        c = Mock(); c.keys.side_effect = [0, 0x80, 0]
        with patch.object(self.b, "wait_keys", return_value=10) as wait:
            with self.assertRaises(bc.BridgeError):
                self.b.t6(c)
        wait.assert_called_once_with(c, 0x81)
        self.assertEqual(c.clear_all.call_count, 3)

    def test_t6_cancelled_queue_rechecked(self):
        c = Mock(); c.keys.side_effect = [0, 0, 0x80, 0]
        with patch.object(self.b, "wait_keys", return_value=10), patch.object(self.b, "wait_frames", return_value=311) as wait:
            with self.assertRaises(bc.BridgeError):
                self.b.t6(c)
        wait.assert_called_once_with(c, 311)

    def test_frame_stall_and_reset_fail(self):
        c = Mock(); c.frame.side_effect = [10, 9]
        with patch.object(self.b.time, "sleep"):
            with self.assertRaises(bc.BridgeError):
                self.b.wait_frames(c, 20)
        c.frame.return_value = 10; c.frame.side_effect = None
        with patch.object(self.b.time, "monotonic", side_effect=[0, 2]):
            with self.assertRaises(bc.BridgeError):
                self.b.wait_frames(c, 20, timeout=1)

    def test_preflight_mismatch_prevents_actions(self):
        c = Mock(host="127.0.0.1", port=8888, retries=0)
        c.version.return_value = "0.3"
        report = self.b.run_checks(c, Path("/unused"), {})
        self.assertFalse(report["all_pass"])
        c.hold_keys.assert_not_called(); c.clear_all.assert_not_called()

    def test_safety_missing_attestation_refused(self):
        with patch.object(self.b.sys, "platform", "win32"):
            with self.assertRaises(ValueError):
                self.b.verify_safety({})

    def test_safety_non_windows_refused(self):
        with patch.object(self.b.sys, "platform", "linux"):
            with self.assertRaises(ValueError):
                self.b.verify_safety({})

    def test_historical_report_untouched(self):
        import hashlib
        self.assertEqual(hashlib.sha256((ROOT / "state/battery_report.json").read_bytes()).hexdigest(),
                         "77b4e1515950a2dc22812a41d35141c00d5c6c641388940e73558112bee3bed0")

    def test_t7_records_first_connection_failure(self):
        c = Mock(host="127.0.0.1", port=8888, retries=0)
        c.version.return_value = bc.BRIDGE_VERSION
        c.info.return_value = (f"version={bc.BRIDGE_VERSION};host=127.0.0.1;port=8888;"
                               "callbacks=ready;maxHold=300;pathPolicy=basename")
        c.call.return_value = "/unused"
        c.keys.return_value = 0
        c.frame.return_value = 10
        c.read8.return_value = 1; c.read16.return_value = 2; c.read32.return_value = 3
        c.read_range_hex.return_value = "00" * 64
        c.call_raw.return_value = ["pong", "10", "<|ERROR|> unknown", "pong"]
        c.ping.side_effect = ["pong", bc.BridgeError("first connection failed")] + ["pong"] * 29
        with patch.object(self.b, "png_size", return_value=(240, 160)), patch.object(
                self.b, "wait_frames", return_value=30), patch.object(self.b, "t5"), patch.object(self.b, "t6"):
            report = self.b.run_checks(c, Path("/unused").resolve(), {})
        self.assertFalse(report["all_pass"])
        self.assertEqual(c.ping.call_count, 31)
        self.assertFalse(next(r for r in report["results"] if r["test"] == "T7")["pass"])
        self.assertTrue(next(r for r in report["results"] if r["test"] == "KEYS_RELEASED")["pass"])

    def test_listener_checks_os_address_pid_and_executable(self):
        import json
        from types import SimpleNamespace
        record = {"Address": "127.0.0.1", "Port": 8888, "Pid": 42, "Executable": "/mgba.exe"}
        manifest = {"mgba_pid": 42, "mgba_executable": "/mgba.exe"}
        for changes in ({}, {"Address": "0.0.0.0"}, {"Pid": 43}, {"Port": 9999}, {"Executable": "/other.exe"}):
            item = dict(record, **changes)
            with self.subTest(changes=changes), patch.object(self.b, "plain_path", side_effect=Path), patch.object(
                    self.b.subprocess, "run", return_value=SimpleNamespace(stdout=json.dumps(item))):
                if changes:
                    with self.assertRaises(ValueError): self.b.verify_listener(manifest)
                else:
                    self.b.verify_listener(manifest)

    def test_changed_protected_hash_fails(self):
        with patch.object(self.b, "sha256", return_value="changed"):
            with self.assertRaises(ValueError):
                self.b.verify_hashes({Path("protected.fixture"): "original"})

    def test_png_decode_and_crc(self):
        import struct
        import zlib
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 240, 160, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(b"\x00" * (160 * (1 + 240 * 3)))) + chunk(b"IEND", b""))
        with patch.object(Path, "read_bytes", return_value=png):
            self.assertEqual(self.b.png_size(Path("fixture")), (240, 160))
        with patch.object(Path, "read_bytes", return_value=png[:-1] + bytes([png[-1] ^ 1])):
            with self.assertRaises(ValueError): self.b.png_size(Path("fixture"))

    def test_new_reports_are_exclusive_and_separate(self):
        import tempfile
        import json
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            manifest = out / "manifest.json"
            manifest.write_text("{}")
            with patch.object(self.b, "verify_safety", return_value=(out, {})), patch.object(
                    self.b, "verify_listener"), patch.object(self.b, "run_checks", return_value={"all_pass": True}), patch.object(
                    sys, "argv", ["battery", "--safety-json", str(manifest)]):
                self.assertEqual(self.b.main(), 0)
                self.assertEqual(self.b.main(), 0)
            reports = list(out.glob("battery-*.json"))
            self.assertEqual(len(reports), 2)
            self.assertTrue(all(json.loads(p.read_text())["all_pass"] for p in reports))


class LuaBridgeTests(unittest.TestCase):
    def test_real_bridge_with_mock_mgba(self):
        import os
        lua = os.environ.get("LUA_BIN") or shutil.which("lua") or shutil.which("texlua")
        self.assertTrue(lua, "Install Lua 5.3+ and/or set LUA_BIN; Lua tests must not be skipped")
        result = subprocess.run([lua, str(Path(__file__).with_name("bridge_harness.lua")),
                                 str(ROOT / "src/FireRedBridgeSocketServer_v0.3.lua")],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)


if __name__ == "__main__":
    unittest.main()
