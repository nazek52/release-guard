# Operator runbook

1. Run fixture replay before connecting new evidence. Only exit 0 permits promotion.
2. On HOLD, inspect the reason: freshness, missing windows, low volume, or wide histogram uncertainty. Collect more data or improve instrumentation; do not change the clock or loosen policy just to obtain PASS.
3. On FAIL, retain report/evidence and reject the candidate. Actual rollback belongs to your deployment controller and approved rollout procedure.
4. On a slow/noisy local host, healthy demo latency may produce HOLD. Use deterministic fixtures to test logic and the measured report to explain environmental effects.
5. Restore the demo with `CANARY_MODE=healthy docker compose up -d --wait canary` (PowerShell: assign `$env:CANARY_MODE='healthy'` first). `docker compose down` stops only this lab.
6. If subnet allocation fails, inspect network overlap and choose LAB_SUBNET. Never prune unrelated networks to run a demonstration.

The default bounds and window lengths are demonstration choices. Agree SLOs, traffic selection, and rollback ownership before integrating a real rollout.
