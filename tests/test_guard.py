from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import pytest
from guard.policy import Policy, evaluate, histogram_interval, InvalidEvidence, wilson

NOW = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)


def observation(n=1000, errors=0, slow=False):
    return {
        "requests": n,
        "errors": errors,
        "latency_ms": [
            {"le": 10, "count": 0},
            {"le": 25, "count": 0 if slow else n},
            {"le": 500, "count": n},
            {"le": "+Inf", "count": n},
        ],
    }


def evidence():
    return {
        "schema_version": 1,
        "windows": [
            {
                "start": (NOW - timedelta(seconds=120 - i * 60)).isoformat(),
                "end": (NOW - timedelta(seconds=60 - i * 60)).isoformat(),
                "baseline": observation(),
                "canary": observation(),
            }
            for i in range(2)
        ],
    }


def test_healthy_passes_and_clear_errors_fail():
    data = evidence()
    assert evaluate(data, now=NOW)["verdict"] == "PASS"
    data["windows"][1]["canary"] = observation(errors=200)
    assert evaluate(data, now=NOW)["verdict"] == "FAIL"


def test_low_volume_holds():
    data = evidence()
    data["windows"][0]["canary"] = observation(n=10)
    assert evaluate(data, now=NOW)["verdict"] == "HOLD"


def test_coarse_histogram_holds_instead_of_guessing_latency():
    data = evidence()
    data["windows"][0]["canary"]["latency_ms"] = [
        {"le": 10, "count": 0},
        {"le": 500, "count": 1000},
        {"le": "+Inf", "count": 1000},
    ]
    assert evaluate(data, now=NOW)["verdict"] == "HOLD"


def test_clear_latency_failure():
    data = evidence()
    data["windows"][0]["canary"]["latency_ms"] = [
        {"le": 200, "count": 0},
        {"le": 500, "count": 1000},
        {"le": "+Inf", "count": 1000},
    ]
    assert evaluate(data, now=NOW)["verdict"] == "FAIL"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["windows"][0].update(end="2026-01-01T01:00:00Z"),
        lambda d: d["windows"][1].update(start="2026-01-01T00:03:30Z"),
        lambda d: d.update(windows=[]),
        lambda d: d["windows"][0]["canary"].update(errors=-1),
        lambda d: d["windows"][0]["canary"].update(requests=True),
        lambda d: d["windows"][0]["canary"].update(latency_ms=[]),
        lambda d: d["windows"][0].update(start="2026-01-01T00:03:00"),
    ],
)
def test_invalid_evidence_fails_closed(mutation):
    data = evidence()
    mutation(data)
    assert evaluate(data, now=NOW)["verdict"] == "HOLD"


def test_stale_metrics_hold():
    assert evaluate(evidence(), now=NOW + timedelta(hours=1))["verdict"] == "HOLD"


def test_invalid_policy_holds():
    assert evaluate(evidence(), replace(Policy(), max_error_rate=2), NOW)["verdict"] == "HOLD"


def test_histogram_rejects_nonmonotonic_and_missing_infinity():
    with pytest.raises(InvalidEvidence):
        histogram_interval(
            [{"le": 10, "count": 10}, {"le": 20, "count": 5}, {"le": "+Inf", "count": 10}], 10
        )
    with pytest.raises(InvalidEvidence):
        histogram_interval([{"le": 10, "count": 1}, {"le": 20, "count": 10}], 10)


def test_zero_errors_has_nonzero_uncertainty():
    lower, upper = wilson(0, 100)
    assert lower == 0 and 0.03 < upper < 0.04
