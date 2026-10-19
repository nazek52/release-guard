import argparse
from dataclasses import fields
import json
from pathlib import Path
import sys
from guard.policy import Policy, evaluate, timestamp


def main():
    parser = argparse.ArgumentParser(
        description="Fail-closed canary gate: PASS=0, FAIL=1, HOLD/invalid=2"
    )
    parser.add_argument("evidence", help="JSON with consecutive baseline/canary windows")
    parser.add_argument("--policy", help="Optional JSON policy overrides")
    parser.add_argument("--now", help="ISO timestamp for deterministic replay; omit in live CI")
    parser.add_argument("--output", help="Write machine-readable report")
    args = parser.parse_args()
    try:
        raw = json.loads(Path(args.policy).read_text()) if args.policy else {}
        if not isinstance(raw, dict) or set(raw) - {f.name for f in fields(Policy)}:
            raise ValueError("Unknown policy keys")
        policy = Policy(**raw)
        path = Path(args.evidence)
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("Evidence exceeds 10 MiB")
        evidence = json.loads(path.read_text())
        result = evaluate(evidence, policy, timestamp(args.now) if args.now else None)
    except (ValueError, OSError, TypeError) as exc:
        result = {"schema_version": 1, "verdict": "HOLD", "reason": f"Invalid input: {exc}"}
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return {"PASS": 0, "FAIL": 1, "HOLD": 2}[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
