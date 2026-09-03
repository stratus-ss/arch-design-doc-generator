# Design: TSR FAIL/WARNING Result line filter

`_extract_leaf_check` strips HTML, then branches on check Status.

Unfiltered (PASS, INFO, SKIPPED, NOT_APPLICABLE): `_condense_result_evidence` then `_clip_evidence`.

FAIL/WARNING: `_keep_important_result_lines` (drop PASS/INFO/SKIP/NA and status-less dumps; keep FAIL/WARNING/LIMITATION plus wrappers with kept children; no ALL NODES / PASS NODES), then `_condense_repeated_node_status_lines` and `_condense_unhealthy_workload_pods`, then clip at 32_000.

CCX `_extract_ccx_check` is unchanged.
