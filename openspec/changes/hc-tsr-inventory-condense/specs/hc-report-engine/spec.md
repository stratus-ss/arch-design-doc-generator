# Health Check Report Engine (`hc-tsr-inventory-condense` delta)

## MODIFIED Requirements

### Requirement: TSR identical pass-host condensation
TSR leaf Result text SHALL collapse fully-ok per-host blocks inside a role node group (`MASTER NODES:::`, `RHCOS NODES:::`, and the same `* NODES` header shape) before clipping. A host entry MAY be `hostname:` plus following status lines, or `hostname:   [PASS]   - reason: …` on one line. A body is fully ok when it has `[PASS]` or `[INFO]` and none of `[FAIL]`, `[WARNING]`, `[WARN]`, `[LIMITATION]`, `[SUPPORT LIMITATION]`, `[SKIP]`, `[SKIPPED]`, `[NOT_APPLICABLE]`, `[NA]`. `{group label}::>ALL NODES:` SHALL be emitted only when every host in that group is fully ok (two or more hosts). A mixed group with two or more fully-ok hosts and at least one non-ok host SHALL emit `{group label}::>PASS NODES:` plus one ok body, SHALL keep every non-ok hostname, and SHALL NOT emit ALL NODES. When every host is fully ok, differing PASS/INFO reason text MAY still collapse to one representative body. Groups that already contain `>ALL NODES:` SHALL be left unchanged. Bare `NODES::` SHALL NOT be a collapse group. After at least one host in a group, a non-empty line with no result-status token (`mtu`, `ipv4.enabled`) SHALL end that group so later `MASTER NODES:::` / `RHCOS NODES:::` blocks still collapse. CCX Message cells SHALL NOT be condensed. Check `status` SHALL NOT change because of condensation.

#### Scenario: Mixed group emits PASS NODES not ALL NODES
- GIVEN a role node group with three hosts where one has `[WARNING]` or `[SUPPORT LIMITATION]` and the other two have PASS-only bodies
- WHEN the leaf Result is parsed
- THEN evidence contains `PASS NODES`
- AND the non-ok hostname remains
- AND the PASS hostnames are absent
- AND that group has no ALL NODES line

## ADDED Requirements

### Requirement: TSR inventory dump condensation
After host condensation and before the 32_000-character clip, TSR leaf Result text SHALL condense inventory dumps. A ` · ` header is a line whose fields all match `^[A-Z][A-Z0-9 /._-]*$`. Data rows contain ` · `, are not headers, and have no result-status token. Signature is fields after the first two. Groups of two or more identical signatures SHALL keep the header (when present), the first row, and `({n} more)`. A run of two or more data rows with no ALL-CAPS header SHALL still group by signature. A non-data line SHALL end the current run; later data rows SHALL form a new run and MAY collapse without a new header. A line containing `(nconnect=` SHALL group by that token; two or more SHALL keep the first line and `({n} more NFS mounts with {token})`. A `node <hostname>:` or `node <hostname> <qualifier>:` line with a result-status token, or the exact trailer `nfs-slot-tuning.service: not active or missing`, SHALL group by qualifier plus status body; two or more SHALL emit `({n} nodes):   {body}` for unqualified lines and `({n} nodes) <qualifier>:   {body}` for qualified lines, and SHALL NOT emit ALL NODES. A line matching `<ns>:<name>   [WARNING]   - looks unhealthy` SHALL group by namespace plus name with trailing `-[a-z0-9]+-[a-z0-9]{5}` stripped; two or more SHALL keep the first line and `({n} more pods)`. Unique rows stay. Check `status` SHALL NOT change.

#### Scenario: Identical table remainders collapse
- GIVEN a `NAMESPACE · VMI · LIVEMIGRATABLE` header and three data rows that share remainder `true`
- WHEN the leaf Result is parsed
- THEN evidence contains the header and one data row
- AND evidence contains `(2 more)`
- AND it does not list all three identity names

#### Scenario: Distinct table remainders stay separate
- GIVEN a `NAMESPACE · NAME · TYPE` header, two rows with remainder `bridge`, and one row with remainder `bond`
- WHEN the leaf Result is parsed
- THEN evidence contains one `bridge` example and `(1 more)`
- AND the `bond` row remains in full

#### Scenario: Headerless table remainders collapse
- GIVEN three ` · ` data rows with no ALL-CAPS header that share remainder `ReadWriteMany · Bound · yes`
- WHEN the leaf Result is parsed
- THEN evidence contains one data row
- AND evidence contains `(2 more)`

#### Scenario: Table resumes after a broken row
- GIVEN a `NAMESPACE · PVC · PHASE · STORAGECLASS` header, two matching data rows, a line with no ` · `, then two more matching data rows
- WHEN the leaf Result is parsed
- THEN evidence contains two `(1 more)` markers
- AND the broken line remains

#### Scenario: Nconnect mounts collapse by token
- GIVEN two NFS mount lines that share `(nconnect=default/1)`
- WHEN the leaf Result is parsed
- THEN evidence contains one mount line
- AND evidence contains `(1 more NFS mounts with (nconnect=default/1))`

#### Scenario: Repeated node warnings collapse without ALL NODES
- GIVEN two `node examplehost061.cl1.cluster.example.com:` WARNING lines with the same reason body
- WHEN the leaf Result is parsed
- THEN evidence contains `(2 nodes):`
- AND evidence does not contain ALL NODES for those lines

#### Scenario: Qualified node status lines collapse
- GIVEN three `node <hostname> cmdline:` INFO lines with the same reason body
- WHEN the leaf Result is parsed
- THEN evidence contains `(3 nodes) cmdline:`
- AND those hostnames are absent

#### Scenario: Unhealthy pods collapse by workload
- GIVEN two WARNING pod lines in the same namespace whose names share a prefix after stripping `-[a-z0-9]+-[a-z0-9]{5}`
- WHEN the leaf Result is parsed
- THEN evidence contains one pod line
- AND evidence contains `(1 more pods)`
