from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import math


class InvalidEvidence(ValueError):
    pass


@dataclass(frozen=True)
class Policy:
    min_requests: int = 300
    max_error_rate: float = 0.02
    max_error_increase: float = 0.02
    max_p95_ms: float = 150
    max_p95_ratio: float = 3
    max_age_seconds: float = 300
    min_window_seconds: float = 1
    max_window_seconds: float = 3600
    consecutive_windows: int = 2

    def validate(self):
        for name, value in asdict(self).items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise InvalidEvidence(f"Policy {name} must be finite and positive")
        if type(self.min_requests) is not int or type(self.consecutive_windows) is not int:
            raise InvalidEvidence("Request and window counts must be integers")
        if self.max_error_rate >= 1 or self.max_error_increase >= 1:
            raise InvalidEvidence("Error rates must be fractions below 1")
        if self.min_window_seconds > self.max_window_seconds:
            raise InvalidEvidence("Invalid policy window range")


def timestamp(value):
    if not isinstance(value, str):
        raise InvalidEvidence("Timestamps must be ISO-8601 strings with timezone")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidEvidence("Invalid timestamp") from exc
    if result.tzinfo is None:
        raise InvalidEvidence("Timestamp timezone required")
    return result.astimezone(timezone.utc)


def wilson(errors, total, z=1.96):
    p = errors / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0, center - spread), min(1, center + spread)


def histogram_interval(buckets, total, quantile=0.95):
    if not isinstance(buckets, list) or len(buckets) < 2:
        raise InvalidEvidence("At least one finite histogram bucket and +Inf are required")
    previous_bound, previous_count = 0.0, 0
    interval = None
    for i, bucket in enumerate(buckets):
        if not isinstance(bucket, dict) or set(bucket) != {"le", "count"}:
            raise InvalidEvidence("Histogram buckets need exactly le and count")
        raw = bucket["le"]
        if raw == "+Inf":
            bound = math.inf
        elif isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
            raise InvalidEvidence("Histogram boundaries must be finite numbers or +Inf")
        else:
            bound = float(raw)
        count = bucket["count"]
        if (
            type(count) is not int
            or count < previous_count
            or count > total
            or bound <= previous_bound
        ):
            raise InvalidEvidence(
                "Histogram bounds/counts must be ordered, cumulative, and within total"
            )
        if math.isinf(bound) and i != len(buckets) - 1:
            raise InvalidEvidence("+Inf must be the last bucket")
        if interval is None and count >= math.ceil(total * quantile):
            interval = (previous_bound, bound)
        previous_bound, previous_count = bound, count
    if not math.isinf(previous_bound) or previous_count != total:
        raise InvalidEvidence("Final +Inf bucket must equal total requests")
    return interval


def observation(row):
    if not isinstance(row, dict):
        raise InvalidEvidence("Observation must be an object")
    total, errors = row.get("requests"), row.get("errors")
    if type(total) is not int or total <= 0 or type(errors) is not int or not 0 <= errors <= total:
        raise InvalidEvidence("Request/error counts must be integers with 0 <= errors <= requests")
    return total, errors, histogram_interval(row.get("latency_ms"), total)


def bounded(value):
    return value if math.isfinite(value) else None


def assess_window(window, policy, now):
    start, end = timestamp(window.get("start")), timestamp(window.get("end"))
    duration = (end - start).total_seconds()
    if end > now or (now - end).total_seconds() > policy.max_age_seconds:
        raise InvalidEvidence("Stale or future metrics window")
    if not policy.min_window_seconds <= duration <= policy.max_window_seconds:
        raise InvalidEvidence("Metrics window duration outside policy")
    bn, be, bp = observation(window.get("baseline"))
    cn, ce, cp = observation(window.get("canary"))
    reasons, failures, uncertain = [], [], []
    if min(bn, cn) < policy.min_requests:
        uncertain.append("Insufficient request volume")
    blo, bhi = wilson(be, bn)
    clo, chi = wilson(ce, cn)

    def compare(label, lower, upper, limit):
        if lower > limit:
            failures.append(label)
        elif upper > limit:
            uncertain.append(label)

    compare("Canary error rate exceeds budget", clo, chi, policy.max_error_rate)
    compare("Error-rate regression exceeds budget", clo - bhi, chi - blo, policy.max_error_increase)
    compare("Canary p95 exceeds absolute latency budget", cp[0], cp[1], policy.max_p95_ms)
    lower_ratio = cp[0] / bp[1] if math.isfinite(bp[1]) else 0
    upper_ratio = cp[1] / bp[0] if bp[0] > 0 else math.inf
    compare(
        "Canary p95 regression exceeds ratio budget", lower_ratio, upper_ratio, policy.max_p95_ratio
    )
    # Low volume may still show a clear failure. Missing evidence never passes.
    verdict = "FAIL" if failures else "HOLD" if uncertain else "PASS"
    reasons = failures + ["Uncertain: " + reason for reason in uncertain]
    return {
        "verdict": verdict,
        "reasons": reasons or ["All conservative bounds satisfy policy"],
        "start": start.isoformat(),
        "end": end.isoformat(),
        "baseline": {
            "requests": bn,
            "errors": be,
            "error_interval_95pct": [blo, bhi],
            "p95_bucket_ms": [bounded(v) for v in bp],
        },
        "canary": {
            "requests": cn,
            "errors": ce,
            "error_interval_95pct": [clo, chi],
            "p95_bucket_ms": [bounded(v) for v in cp],
        },
        "p95_ratio_interval": [bounded(lower_ratio), bounded(upper_ratio)],
    }


def evaluate(evidence, policy=None, now=None):
    policy = policy or Policy()
    now = now or datetime.now(timezone.utc)
    result = {
        "schema_version": 1,
        "policy": asdict(policy),
        "evaluated_at": now.isoformat(),
        "windows": [],
        "action": "No deployment mutation is performed",
    }
    try:
        policy.validate()
        if now.tzinfo is None:
            raise InvalidEvidence("Evaluation time must include timezone")
        if not isinstance(evidence, dict) or evidence.get("schema_version") != 1:
            raise InvalidEvidence("Evidence schema_version must be 1")
        windows = evidence.get("windows")
        if not isinstance(windows, list) or len(windows) < policy.consecutive_windows:
            raise InvalidEvidence("Not enough consecutive windows")
        if len(windows) > 100:
            raise InvalidEvidence("Maximum 100 windows per evaluation")
        previous_end = None
        for window in windows:
            if not isinstance(window, dict):
                raise InvalidEvidence("Window must be an object")
            start, end = timestamp(window.get("start")), timestamp(window.get("end"))
            if previous_end is not None and start != previous_end:
                raise InvalidEvidence("Windows must be consecutive, ordered, and non-overlapping")
            previous_end = end
            result["windows"].append(assess_window(window, policy, now))
        verdicts = [row["verdict"] for row in result["windows"]]
        result["verdict"] = (
            "FAIL" if "FAIL" in verdicts else "HOLD" if "HOLD" in verdicts else "PASS"
        )
        result["reason"] = {
            "PASS": "Every window passed the conservative gate",
            "HOLD": "More or finer evidence is required; do not promote",
            "FAIL": "A budget violation was detected; reject this candidate",
        }[result["verdict"]]
    except (InvalidEvidence, TypeError, KeyError, OverflowError) as exc:
        result.pop("policy", None)
        result.update(verdict="HOLD", reason=f"Invalid evidence: {exc}")
    return result
