# Change Proposal: hc-native-node-expected

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`. Do not modify the living spec until the Doc Update task.

Live **core** SHALL emit one cluster rollup `7.6.node.expected_limits` from existing Prometheus collect `10_metrics/node_cpu_limits_pct.json` and `10_metrics/node_memory_limits_pct.json`. Missing both payloads (`_is_missing`) SHALL be SKIPPED. The engine SHALL parse Prometheus vectors with label `node` (`by (node)`). FAIL if any sample is ≥ 90. WARNING if any sample is ≥ 80 and none is ≥ 90. Else PASS. Evidence SHALL list node and percent. The engine SHALL NOT emit per-node check_ids. Stub `7.6.node_expected` SHALL remain SKIPPED. `7.6.tsr.6_1_3_2_node_expected_resource_consumption` SHALL be a sparse alias of `7.6.node.expected_limits`. The engine SHALL NOT retune `7.8.node.*.alloc`. The engine SHALL NOT use `oc adm top` as the bar. Collect SHALL NOT add a new query.

## Why

TSR FAIL is limits near 90% of node allocatable. Live already collects those percents. Native `7.6.node_expected` is a SKIPPED stub. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_node_expected_2026-08-29.md`
