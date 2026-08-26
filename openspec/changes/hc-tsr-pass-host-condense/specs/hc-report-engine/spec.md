# Health Check Report Engine (`hc-tsr-pass-host-condense` delta)

## MODIFIED Requirements

### Requirement: TSR Result length
TSR Result HTML SHALL NOT be sliced at 2000 characters. Parsed evidence SHALL be condensed (identical PASS/INFO host groups) and then clipped at 32_000 characters with a truncation marker.

#### Scenario: Text past 2000 characters is kept
- GIVEN TSR HTML whose Result cell exceeds 2000 characters and is under 32_000 after condensation
- WHEN it is parsed
- THEN characters after offset 2000 remain in evidence

#### Scenario: Oversized Result is clipped
- GIVEN TSR HTML whose Result cell exceeds 32_000 characters after condensation
- WHEN it is parsed
- THEN evidence length is at most 32_000
- AND the evidence ends with the truncation marker

## ADDED Requirements

### Requirement: TSR identical pass-host condensation
TSR leaf Result text SHALL collapse fully-ok per-host blocks inside a role node group (`MASTER NODES:::`, `RHCOS NODES:::`, and the same `* NODES` header shape) before clipping. A host entry MAY be `hostname:` plus following status lines, or `hostname:   [PASS]   - reason: …` on one line. A body is fully ok when it has `[PASS]` or `[INFO]` and none of `[FAIL]`, `[WARNING]`, `[WARN]`, `[LIMITATION]`, `[SUPPORT LIMITATION]`, `[SKIP]`, `[SKIPPED]`, `[NOT_APPLICABLE]`, `[NA]`. `{group label}::>ALL NODES:` SHALL be emitted only when every host in that group is fully ok (two or more hosts). A mixed group (any non-ok host) SHALL keep every hostname and SHALL NOT emit ALL NODES. When every host is fully ok, differing PASS/INFO reason text MAY still collapse to one representative body. Groups that already contain `>ALL NODES:` SHALL be left unchanged. Bare `NODES::` SHALL NOT be a collapse group. After at least one host in a group, a non-empty line with no result-status token (`mtu`, `ipv4.enabled`) SHALL end that group so later `MASTER NODES:::` / `RHCOS NODES:::` blocks still collapse. CCX Message cells SHALL NOT be condensed. Check `status` SHALL NOT change because of condensation.

#### Scenario: Identical worker PASS hosts collapse
- GIVEN a TSR Result with `RHCOS NODES:::` and two or more hosts whose bodies are identical PASS-only lines
- WHEN the leaf Result is parsed
- THEN evidence contains `RHCOS NODES::>ALL NODES:`
- AND it contains one copy of that PASS body
- AND it does not list each of those worker hostnames

#### Scenario: Mixed group does not emit ALL NODES
- GIVEN a role node group with three hosts where one has `[WARNING]` or `[SUPPORT LIMITATION]` and the other two have identical PASS-only bodies
- WHEN the leaf Result is parsed
- THEN every hostname in that group remains in evidence
- AND that group has no ALL NODES line

#### Scenario: Independent groups collapse independently
- GIVEN `MASTER NODES:::` with a `[SUPPORT LIMITATION]` host and `RHCOS NODES:::` with identical PASS-only hosts
- WHEN the leaf Result is parsed
- THEN the MASTER LIMITATION hostname remains
- AND RHCOS PASS hosts collapse to `RHCOS NODES::>ALL NODES:`

#### Scenario: All-ok group collapses even when PASS reasons differ
- GIVEN two hosts in the same role group with different PASS reason text
- WHEN the leaf Result is parsed
- THEN evidence contains `RHCOS NODES::>ALL NODES:`
- AND those hostnames are absent

#### Scenario: Heterogeneous ok bodies collapse when every host is ok
- GIVEN a role node group with four hosts: two share PASS body A, two share PASS body B (different from A)
- WHEN the leaf Result is parsed
- THEN evidence contains `RHCOS NODES::>ALL NODES:`
- AND those hostnames are absent

#### Scenario: Native ALL NODES is not rewritten
- GIVEN Result text that already contains `RHCOS NODES::>ALL NODES:`
- WHEN the leaf Result is parsed
- THEN that ALL NODES line remains
- AND no extra host lines are invented for that group

#### Scenario: Inline hostname PASS lines collapse
- GIVEN `RHCOS NODES:::` hosts whose status is on the same line as the hostname (`hostname:   [PASS]   - reason: …`)
- WHEN the leaf Result is parsed
- THEN evidence contains `RHCOS NODES::>ALL NODES:`
- AND those hostnames are absent

#### Scenario: Repeated field groups keep labels and collapse each block
- GIVEN `state` then `MASTER NODES:::` / `RHCOS NODES:::` PASS hosts, then `mtu`, then another `MASTER NODES:::` / `RHCOS NODES:::` PASS block
- WHEN the leaf Result is parsed
- THEN `state` and `mtu` remain
- AND each role group collapses independently
- AND worker hostnames are absent
