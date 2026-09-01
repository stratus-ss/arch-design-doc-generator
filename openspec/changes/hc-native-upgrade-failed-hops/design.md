# Design: native ClusterVersion failed or partial hops

Mint `7.6.upgrade.failed_hops` from existing `08_day2/clusterversion.json`. Do not retune `_evaluate_upgrade_history`. Do not retarget `7.6.tsr.6_2_1_update_history`.

Resolve List or named ClusterVersion via `_cluster_version_object`. `_hc_error` on the payload or object is SKIPPED. Missing, `_hc_not_found`, or empty history is NOT_APPLICABLE. Any history item whose `state` is exactly `Partial` or `Failed` is FAIL. Else PASS. Never WARNING.

Scoring matrix and TSR freeze are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
