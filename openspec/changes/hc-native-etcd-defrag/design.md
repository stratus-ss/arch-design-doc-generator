# Design: native etcd fragmentation rollup

Mint `7.8.etcd.defrag` from existing `etcd_db_size_bytes` and `etcd_db_size_in_use`. Do not add collect. Do not add oc logs for defrag. Do not retune per-member DB size 4GiB/8GiB bars.

Match pods between the two Prometheus vectors. Reuse `_parse_prometheus_vector`. Dispatch from `_evaluate_etcd_performance` after `_evaluate_etcd_db_size` without changing that function.

Scoring matrix is in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
