# Health Check Report Engine (`hc-live-parity-content-from` delta)

## ADDED Requirements

### Requirement: CONTENT_FROM rows MAY alias to a native check_id
Plan 1 CONTENT_FROM KB rows MAY be sparse aliases (`content_from` plus title and finding flags). The target SHALL be a native `check_id` when one exists, otherwise a non-alias canonical. Loader fail-closed rules (single hop, no overlay, exact target) SHALL remain unchanged.

#### Scenario: Sparse alias inherits native prose
- GIVEN a CONTENT_FROM alias with `content_from` set to a native `check_id` and omitted inherited keys
- WHEN `load_kb()` runs
- THEN the alias recommendation, verification, description, impact, and links equal the native row
- AND the alias `check_id` and title stay local

### Requirement: New CONTENT_FROM aliases omit Chapter 6 findings
New aliases created for Plan 1 CONTENT_FROM rows SHALL set `include_in_findings = false`. Chapter 7 MAY still list the alias check. The native target remains eligible for Chapter 6.

#### Scenario: New alias is not a Chapter 6 finding
- GIVEN a new CONTENT_FROM alias with `include_in_findings = false`
- WHEN `derive_findings` runs on a FAIL or WARNING for that alias `check_id`
- THEN that alias `check_id` does not appear as a finding or finding-group member
- AND chapter 7 may still list the check

### Requirement: Virt CONTENT_FROM SHALL NOT dump onto identification-and-state
OpenShift Virtualization TSR 4.8 leaves SHALL alias to native `7.4.cnv.state`, `7.4.cnv.kubevirt`, `7.4.cnv.pods`, or `7.4.cnv.live_migratable` by story. Distinct virt TSR prose rows SHALL remain canonical. The set of virt aliases SHALL NOT all target `7.4.tsr.4_8_1_1_1_identification_and_state`.

#### Scenario: Virt family uses native CNV targets
- GIVEN virt CONTENT_FROM aliases after this change
- WHEN `load_kb()` resolves those aliases
- THEN at least one alias has `content_from` equal to a `7.4.cnv.*` native id
- AND not every virt alias has `content_from = "7.4.tsr.4_8_1_1_1_identification_and_state"`
