# Design: 7.5/7.6 sparse aliases and node-load rollup

Keep kubelet Ready as WARNING (`7.5.kubelet_health`). Do not FAIL Ready. Keep pod restarts as per-container `restartCount > 10`. Keep upgrade history as PASS when any hop is Completed; do not FAIL Partial/Failed.

Mint `7.5.node.utilization` as worst-of per-node `7.5.node.{short}.utilization` (WARNING > INFO > PASS). Missing, empty, or unparseable `top_nodes` SHALL emit NOT_APPLICABLE on both `7.5.node_util` and `7.5.node.utilization`. Do not retune CPU/mem percents. Do not drop per-node ids.

Sparse-alias kubelet, restarts, update-history, node-load leaf, and node-load parent onto those natives (`include_in_findings = false`). Set `include_in_findings = false` on existing pod/job/namespace pruning hops and parent `7.6.tsr.6_1_5_pruning`. Alias rows SHALL NOT overlay inherited narrative keys.

Do not alias quota leaf, requests-and-limits, netpol pruning, or images patch management. Do not retarget `7.6.tsr.6_3_1_active_alerts`.

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
