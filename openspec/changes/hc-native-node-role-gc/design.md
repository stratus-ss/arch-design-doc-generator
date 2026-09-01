# Design: native node-role KB alias and image GC aggregate

Keep `7.5.node_roles` as missing-label only. Add full-voice KB for that native. Sparse-alias `7.5.tsr.5_6_node_role_values` to `7.5.node_roles`. Do not fold taints or infra-intent into node_roles. Do not change `7.5.master_taints` scoring.

Mint `7.6.node.image_gc` as one aggregate check_id. FAIL if any scored node `used_percent >= high_percent`. Else WARNING if any scored node `used_percent >= 50`. Else PASS. Missing node-proxy payload is INFO n/a. Per-node HIGH comes from applied `configz` `imageGCHighThresholdPercent` when present, else named constant **85**. Early warning bar is named constant **50**. Those constants are changeable later without a new collect shape.

Live `08_day2` MAY write `node_image_gc.json` (counts, bytes, percents only). Supportshell MAY omit it (`hc_info` only; no node proxy). Collect SHALL NOT persist full kubelet `configz` or `stats/summary` trees.

Sparse-alias `7.6.tsr.6_1_5_5_node_garbage_collection` to `7.6.node.image_gc`. Alias rows SHALL NOT overlay inherited narrative keys.

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
