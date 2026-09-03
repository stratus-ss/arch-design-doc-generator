# Health Check Report Engine (`hc-ch6-tsr-ref-correctness` delta)

## ADDED Requirements

### Requirement: §6.2 TSR ref is the TSR HTML section number
§6.2 SHALL print `**TSR ref:**` followed by dotted section number(s) from member `CheckResult.tsr_ref` values that match `^\d+(?:\.\d+)+$`, unique, first-seen order, space-separated. If none match, SHALL print `n/a`. SHALL NOT parse the finding title for this line. SHALL NOT emit a hyperlink.

#### Scenario: KB title without numeric prefix
- GIVEN check `7.4.tsr.4_8_1_1_1_identification_and_state` with `tsr_ref` `4.8.1.1.1` and KB title `TSR CNV identification and state`
- WHEN §6.2 is rendered
- THEN the line is `**TSR ref:** 4.8.1.1.1`
- AND the line is not `n/a`

#### Scenario: CCX or deterministic
- GIVEN `tsr_ref` empty or `CCX:internal`
- WHEN §6.2 is rendered
- THEN the line is `**TSR ref:** n/a`

#### Scenario: grouped distinct leaves
- GIVEN two members with `tsr_ref` `4.5.2` and `4.5.4.1`
- WHEN §6.2 is rendered
- THEN the line is `**TSR ref:** 4.5.2 4.5.4.1`
