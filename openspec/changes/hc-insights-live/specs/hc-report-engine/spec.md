# Health Check Report Engine (`hc-insights-live` delta)

## ADDED Requirements

### Requirement: Insights CCX CVE ingest bars
Core `evaluate_ccx` SHALL emit a row for each id in `CCX_STATIC_CHECK_IDS`. When InsightsOperator reporting is disabled (`spec.disabled`, `status.disabled`, or `spec.disableInsightsReporting` is true), each of those rows SHALL be `NOT_APPLICABLE`. Else when `12_ccx/ccx_rules` is missing, `_hc_not_found`, or `_hc_error`, each unmatched row SHALL be `SKIPPED` and evidence SHALL name `HC_CCX_RULES_FILE` and Insights Available. Else when a payload row matches a CVE, status SHALL follow the existing `_status` mapping of that payload. Else unmatched CVE ids SHALL be `SKIPPED`. Missing `HC_CCX_RULES_FILE` SHALL never FAIL. Evaluation SHALL NOT scrape Insights/Advisor HTTP APIs.

#### Scenario: disabled InsightsOperator is NOT_APPLICABLE
- GIVEN InsightsOperator with `spec.disabled` true
- WHEN `evaluate_ccx` runs
- THEN each `CCX_STATIC_CHECK_IDS` status is `NOT_APPLICABLE`
- AND the status is not `FAIL`

#### Scenario: missing rules file is SKIPPED
- GIVEN InsightsOperator reporting is not disabled
- AND `12_ccx/ccx_rules` has `_hc_not_found`
- WHEN `evaluate_ccx` runs
- THEN each `CCX_STATIC_CHECK_IDS` status is `SKIPPED`
- AND evidence contains `HC_CCX_RULES_FILE`
- AND the status is not `FAIL`

#### Scenario: matched payload keeps mapped status
- GIVEN a `ccx_rules` payload whose title matches `CVE-2026-31431`
- AND payload `status` is `PASS`
- WHEN `evaluate_ccx` runs
- THEN `7.7.ccx_external.cve_2026_31431_copy_fail_in_algif_aead` status is `PASS`
- AND the status is not `SKIPPED`

#### Scenario: unmatched CVE is not FAIL
- GIVEN a `ccx_rules` payload that does not mention the static CVE ids
- WHEN `evaluate_ccx` runs
- THEN each unmatched `CCX_STATIC_CHECK_IDS` status is `SKIPPED`
- AND the status is not `FAIL`

## MODIFIED Requirements

None.
