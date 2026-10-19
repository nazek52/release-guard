# Decisions and guarantees

## 1. Three outcomes instead of a boolean
A boolean encourages treating missing evidence as success. PASS requires all bounds to satisfy every rule. FAIL means a lower bound already violates a budget. HOLD covers uncertainty and invalid evidence. Exit 2 must block promotion just like exit 1, while allowing the operator to distinguish collecting more data from rejecting a candidate.

## 2. Histogram intervals
A cumulative bucket only says where a percentile lies. Linear interpolation would invent detail the input never measured. We propagate lower/upper bounds through absolute and ratio comparisons. This can hold a healthy release when buckets are coarse; finer buckets near the policy threshold are the appropriate fix.

## 3. Evidence separated from mutation
The gate produces a report and an exit code. It has no kubeconfig, cloud credentials, or rollback permissions. A deployment controller can consume PASS, but must own rollout and rollback policy separately. This makes replay and review safe and deterministic.

## 4. Statistical scope
Wilson intervals handle low error counts better than a normal approximation. Combining two marginal intervals is not a formal sequential test. Neither two consecutive windows nor a 95% interval controls the global false-positive rate under repeated peeking. Production adoption requires traffic comparability, agreed budgets, and an explicit experiment/rollout protocol.

## Contract
One window holds baseline and candidate observations for the same time range. Windows must be ordered with exact shared boundaries, finite positive durations, and recent end times. Every histogram ends with +Inf equal to its request count. The parser caps evidence at 10MiB and 100 windows. A malformed later window invalidates promotion even if earlier windows passed.
