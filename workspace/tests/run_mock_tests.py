"""Run the entire offline suite and write a fresh JSON report outside the checkout."""
import json
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main():
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent / "mock"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "time": datetime.now(timezone.utc).isoformat(),
        "kind": "offline mocks, not live emulator testing",
        "tests_run": result.testsRun,
        "failures": [{"test": str(t), "traceback": text} for t, text in result.failures],
        "errors": [{"test": str(t), "traceback": text} for t, text in result.errors],
        "skipped": [{"test": str(t), "reason": reason} for t, reason in result.skipped],
        "all_pass": result.wasSuccessful() and result.testsRun > 0 and not result.skipped,
    }
    output = Path(tempfile.gettempdir()) / ("firered-mocks-" + uuid.uuid4().hex + ".json")
    with output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Mock report: {output}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
