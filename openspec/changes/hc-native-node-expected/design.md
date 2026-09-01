# Design: native node expected limits

Mint `7.6.node.expected_limits` from existing `10_metrics/node_cpu_limits_pct` and `node_memory_limits_pct` Prometheus vectors. Reuse `_parse_prometheus_vector` and `_prometheus_value` from `_common.py`. Do not copy a second parser into `day2.py`. Do not edit `10_metrics.sh`. Do not retune 7.8 node alloc. Do not use `oc adm top`. Keep stub `7.6.node_expected` SKIPPED.

Scoring matrix is in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
