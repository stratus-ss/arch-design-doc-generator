# Design: TSR inventory dump condensation

`_extract_leaf_check` already strips HTML, condenses identical PASS/INFO
host groups, then clips at 32_000 characters. Remaining dumps are not
host PASS groups: ` · ` inventory tables, `(nconnect=…)` mount lines,
`node fqdn:` / `node fqdn qualifier:` clones, mixed PASS/WARNING host groups, and
`ns:pod [WARNING] - looks unhealthy` replica lists.

`_condense_result_evidence` chains, in order: host condense (ALL NODES
when every host is ok; PASS NODES when two or more hosts are ok and at
least one is not) → dot-table remainder groups → nconnect token groups →
repeated node-status bodies → unhealthy-pod workload groups. Clip stays
in `_extract_leaf_check` after that chain.

Count markers are `({n} more)`, `({n} more NFS mounts with {token})`,
`({n} nodes):   {body}` (or `({n} nodes) <qualifier>:   {body}`), and
`({n} more pods)`. CCX `_extract_ccx_check` is unchanged.
