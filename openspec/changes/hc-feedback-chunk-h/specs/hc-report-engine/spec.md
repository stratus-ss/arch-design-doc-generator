# Health Check Report Engine (Chunk H delta)

## MODIFIED Requirements

### Requirement: Chapter 4 and §6.1 summary text
Chapter 4 SHALL render the P0/P1 count lines and the same three-column table (Priority, Finding, Summary) previously used in §6.1. Summary cell text SHALL still be `summary_patterns` then FAIL / WARNING / LIMITATION reason, never KB `description`, capped at 220 with terminator-safe truncation (`.!?` plus whitespace, else comma/semicolon, else word boundary). §6.1 SHALL NOT duplicate that table when any P0/P1 finding exists; it SHALL point at Chapter 4. Slot names `{CRITICAL_FINDINGS_SUMMARY}` and `{CRITICAL_FINDINGS}` SHALL NOT change. P2/P3 SHALL NOT appear in the table.

#### Scenario: Pattern wins over emptyDir KB description
- GIVEN a P1 finding for `7.3.tsr.3_7_2_monitoring_storage_type` whose evidence mentions RWX/file storage
- WHEN Chapter 4 is rendered
- THEN the Summary cell mentions block storage or RWX/file storage
- AND it does not contain `emptyDir`
- AND §6.1 does not contain the Priority table

#### Scenario: FAIL reason used when no pattern matches
- GIVEN a synthetic check with no `summary_patterns` and evidence `widget check: [FAIL] - reason: widgets are on fire`
- WHEN Chapter 4 is rendered
- THEN the Summary cell contains `Widgets are on fire`
- AND §6.1 is the pointer `P0 and P1 findings are listed in Chapter 4.`

#### Scenario: Unusable reason is omitted
- GIVEN evidence `[FAIL] - reason: n/a`
- WHEN Chapter 4 is rendered
- THEN the finding id and title still appear
- AND `n/a` is not used as the summary body

#### Scenario: Truncation prefers a real sentence end
- GIVEN a FAIL reason whose first sentence is under 220 characters and a long second sentence
- WHEN Chapter 4 is rendered
- THEN the first sentence is kept
- AND a `.` inside a dotted token such as `pxd.portworx.com` is not treated as a sentence end

#### Scenario: Chapter 4 is the table and §6.1 is a pointer
- GIVEN one or more P0/P1 findings
- WHEN the report is rendered
- THEN `{CRITICAL_FINDINGS_SUMMARY}` contains `| Priority |` and P0/P1 count lines
- AND `{CRITICAL_FINDINGS}` is `P0 and P1 findings are listed in Chapter 4.`
- AND `{CRITICAL_FINDINGS}` does not contain `| Priority |`
- AND P2/P3 findings are not in the Chapter 4 table

#### Scenario: No critical findings
- GIVEN no P0 or P1 findings
- WHEN the report is rendered
- THEN Chapter 4 is `_No critical findings._`
- AND §6.1 is `_No critical or high-priority findings identified._`

### Requirement: §6.2 Observation assembly
§6.2 Observation SHALL be the status-count sentence when square-bracket tags exist, then **exactly one** prose block: KB `summary_patterns` text if matched, otherwise the cleaned first FAIL, else WARNING, else LIMITATION / SUPPORT LIMITATION remainder. When a pattern matches, the TSR remainder SHALL NOT also be printed. Extracted remainder SHALL cap at 400 characters. Pattern sentences and Chapter 4 summaries SHALL cap at 220. Truncation SHALL use a real sentence terminator (`.!?` followed by whitespace or end of string), else last comma/semicolon, else word boundary, and SHALL NOT cut inside a token. Unusable extracted text SHALL be omitted. `[LIMITATION]` and `[SUPPORT LIMITATION]` SHALL be counted as `N LIMITATION` and SHALL be extractable; they SHALL NOT promote the leaf `CheckResult.status` or finding priority to P1.

#### Scenario: Pattern suppresses raw remainder
- GIVEN tagged evidence that matches a `summary_patterns` row and a distinct FAIL remainder containing `access modes include`
- WHEN Observation is rendered
- THEN it contains `sub-checks evaluated`
- AND it contains the pattern sentence (block storage / RWX/file)
- AND it does not contain `access modes include`
- AND it does not contain `emptyDir`

#### Scenario: FAIL reason without a pattern
- GIVEN tagged evidence with no matching pattern
- WHEN Observation is rendered
- THEN Observation contains the cleaned FAIL remainder
- AND it contains the count sentence

#### Scenario: LIMITATION remainder is extracted
- GIVEN evidence with `[LIMITATION] - reason: cluster is in maintenance support; consider an update` and no matching pattern
- WHEN Observation is rendered
- THEN Observation contains `maintenance support`

#### Scenario: LIMITATION tags appear in the count
- GIVEN two PASS tags and two LIMITATION tags
- WHEN Observation is rendered
- THEN the count sentence includes `2 LIMITATION` (or `**2** LIMITATION`)
- AND those tags are not counted only as INFO/N/A

#### Scenario: Dotted CSI names are not sentence ends
- GIVEN a FAIL remainder longer than the remainder cap that contains `pxd.portworx.com` with no `.`+whitespace terminator before that name
- WHEN Observation is rendered
- THEN it does not end with the dangling form `pxd.portworx.`

#### Scenario: Short FAIL remainder keeps the line tail
- GIVEN `scc: [FAIL] - reason: edited:` followed by a JSON line `{"allowedFlexVolumes": "placeholder"}`
- WHEN Observation is rendered
- THEN Observation contains `allowedFlexVolumes` or `placeholder`
- AND it is not only `Edited.`

#### Scenario: Grouped Affected lists two names then a count
- GIVEN `Finding.description` starting with `Affected: node-a, node-b, node-c, node-d`
- WHEN Observation is rendered
- THEN it contains `node-a` and `node-b`
- AND it contains `and 2 more` and `See evidence for the full list`
- AND it does not contain `node-d`
- AND `Finding.description` itself still contains all four names

#### Scenario: Untagged evidence uses pattern and 220 cap
- GIVEN untagged evidence that matches a webhook `summary_patterns` `contains` value and is longer than 220 characters
- WHEN Observation is rendered
- THEN the pattern wording appears
- AND a distinctive tail past the cap does not appear
- AND no `sub-checks evaluated` sentence is emitted

#### Scenario: Unusable extracted reason is omitted
- GIVEN `[FAIL] - reason: n/a` and no matching pattern
- WHEN Observation is rendered
- THEN `n/a` is not printed as Observation prose

## ADDED Requirements

### Requirement: Node Disk Level of Impact is virt StorageClass
`7.4.tsr.4_8_1_3_4_node_disk` impact fields SHALL describe annotating a default virt StorageClass, not evacuating VMs for node disk pressure. Title, Description, and Recommendation SHALL remain the Chunk G virt-StorageClass text.

#### Scenario: LoI is none and StorageClass-scoped
- GIVEN `7.4.tsr.4_8_1_3_4_node_disk`
- WHEN Level of Impact is rendered
- THEN `impact` is `none` (visible **None**)
- AND the detail mentions StorageClass
- AND the detail does not mention evacuating VMs or DiskPressure
