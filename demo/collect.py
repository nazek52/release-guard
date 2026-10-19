"""Collect two real HTTP windows from the loopback-only Compose demo."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

BOUNDS = [10, 25, 50, 100, 150, 250, 500, 1000, 5000]


def now():
    return datetime.now(timezone.utc)


def request(port):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/work", timeout=3) as response:
            failed = response.status >= 500
    except (urllib.error.URLError, TimeoutError, OSError):
        failed = True
    return (time.perf_counter() - started) * 1000, failed


def sample(port, n):
    with ThreadPoolExecutor(max_workers=4) as pool:
        samples = list(pool.map(request, [port] * n))
    return {
        "requests": n,
        "errors": sum(int(failed) for _, failed in samples),
        "latency_ms": [
            {"le": bound, "count": sum(latency <= bound for latency, _ in samples)}
            for bound in BOUNDS
        ]
        + [{"le": "+Inf", "count": n}],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/evidence.json")
    parser.add_argument("--requests", type=int, default=400)
    args = parser.parse_args()
    if not 300 <= args.requests <= 10000:
        parser.error("requests must be between 300 and 10000")
    windows = []
    start = now()
    for _ in range(2):
        with ThreadPoolExecutor(max_workers=2) as pool:
            baseline = pool.submit(sample, 18081, args.requests)
            canary = pool.submit(sample, 18082, args.requests)
            baseline, canary = baseline.result(), canary.result()
        end = now()
        windows.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "baseline": baseline,
                "canary": canary,
            }
        )
        start = end
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "real HTTP traffic against controlled local demo",
                "windows": windows,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Wrote {path}; run python -m guard {path}")


if __name__ == "__main__":
    main()
