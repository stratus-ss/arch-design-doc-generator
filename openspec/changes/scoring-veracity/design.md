# Design: scoring veracity

Python evaluators remain the scorer. This change adjusts status assignment for named checks and adds `CheckResult.scoring_basis`.

Chapter 7 renders a **Scoring** row only for FAIL and WARNING: `Doc-backed` when `scoring_basis == "doc_backed"`, otherwise `Engine policy` (including empty).

Compact/SNO uses `is_compact_cluster(items, masters)` from `_shared_checks`. Automatic approval skips `kubevirt-hyperconverged`. WAL FAIL is P99 `> 10` ms. Backend commit never FAIL/WARNING. Native 7.3 etcd placeholder SKIPPED rows are removed.
