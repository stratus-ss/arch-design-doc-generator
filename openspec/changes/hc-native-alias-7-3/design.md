# Design: 7.3 sparse aliases and platform-operator rollup

Keep per-operator `7.3.co.{name}` bars frozen (`find_degraded_operators` FAIL; Available/Progressing WARNING). Do not drop those rows. Do not delete exact KB `7.3.co.kube-apiserver`.

Mint `7.3.co.platform` as worst-of those per-operator statuses (FAIL > WARNING > PASS). Do not re-read ClusterOperator conditions in the rollup. Missing clusteroperators SHALL emit NOT_APPLICABLE on both `7.3.co` and `7.3.co.platform`. Exact `7.3.co.platform` beats glob `7.3.co.*`.

Sparse-alias 3.2.1 and parent 3.2 onto the rollup. Park additional-operators and leftover-operators CCX on the same rollup (legal single hop). Move CRD TSR onto `7.3.crds` (not the rollup). Alias ingress sharding onto `7.3.ingress.sharding`. Alias MCP TSR and 5.2 onto `7.3.misc.mcp`. Alias rows SHALL NOT overlay inherited narrative keys.

Do not alias `7.3.tsr.3_9_5_csi_drivers`. Do not alias 3.2.1 onto `7.5.operator_state`. Do not alias 3.15 onto `7.5.mcp_health`. Do not retune CRD >500, sharding selectors, or MCP degraded/updating.

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
