# Verification record

Executed 2026-10-19 with Python 3.13.5 and Docker Desktop Linux containers.

- **15 unit tests passed** covering statistical bounds, low volume, coarse histograms, clear regressions, invalid counters, timezones, stale/overlapping windows, policy validation and histogram consistency.
- Four deterministic CLI fixture replays returned the expected exit codes: healthy **0**, degraded **1**, low volume **2**, stale **2**.
- Real HTTP collection against two local containers: two consecutive windows, **400 requests per arm per window**. Healthy baseline/candidate had zero errors and the gate returned **PASS**.
- Controlled degraded candidate: **80 errors out of 400 requests in each window**, baseline zero errors. Gate returned **FAIL / exit 1**. Candidate p95 fell in the 150–250ms bucket, baseline in 25–50ms.

Measured artifacts: [healthy report](evidence/healthy-report.json), [degraded report](evidence/degraded-report.json), [healthy input](evidence/evidence.json), [degraded input](evidence/degraded.json). They contain actual **local synthetic-service HTTP measurements**, not production telemetry. Replay them with their report's `evaluated_at` via `--now`; live runs must use the real current clock.

The host's automatic Docker subnet pool was exhausted by preexisting networks. The lab now uses an explicit configurable subnet; no unrelated networks were removed. Default `LAB_SUBNET` is `10.203.42.0/24`.

Not established: production false-positive/negative rates, statistically controlled sequential testing, Kubernetes integration, or public deployment. CI repeats the two-container experiment and uploads its own evidence.
