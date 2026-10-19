"""Replay checked-in, synthetic evidence with a fixed evaluation clock."""

from pathlib import Path
import subprocess
import sys

for name, expected in [("healthy", 0), ("degraded", 1), ("low-volume", 2), ("stale", 2)]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "guard",
            str(Path("examples") / (name + ".json")),
            "--now",
            "2026-01-01T00:05:00Z",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != expected:
        raise SystemExit(
            f"{name}: expected {expected}, got {result.returncode}\n{result.stdout}\n{result.stderr}"
        )
    print(f"{name}: correct exit code {expected}")
