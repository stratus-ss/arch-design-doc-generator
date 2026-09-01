# Health Check Report Engine (`hc-chapter7-alias-hide` delta)

## ADDED Requirements

### Requirement: Chapter 7 omits content_from aliases
Chapter 7 check-result tables and category stats SHALL omit a check when its KB entry has a non-empty `content_from`. A check with no KB entry or with empty `content_from` SHALL appear. CCX checks without `content_from` SHALL appear. `include_in_findings` SHALL continue to govern Chapter 6 only.

#### Scenario: Alias row omitted from Chapter 7
- GIVEN a `CheckResult` whose KB entry has non-empty `content_from`
- WHEN `_build_check_results_table` renders that category
- THEN the alias KB title is absent from the table

#### Scenario: Native row kept in Chapter 7
- GIVEN a `CheckResult` whose KB entry has empty `content_from`
- WHEN `_build_check_results_table` renders that category
- THEN the native KB title is present in the table

#### Scenario: Chapter 6 findings ignore the Chapter 7 filter
- GIVEN a native FAIL check that is eligible for findings
- WHEN `derive_findings` runs
- THEN a finding for that native `check_id` is present
