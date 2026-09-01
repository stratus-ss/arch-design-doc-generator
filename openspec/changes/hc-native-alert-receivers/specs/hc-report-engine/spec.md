# Health Check Report Engine (`hc-native-alert-receivers` delta)

## ADDED Requirements

### Requirement: Native Alertmanager receiver scoring
Core evaluation SHALL emit `7.6.alert_receivers` with title `Alert receivers`. The engine SHALL read `results["08_day2"]["alertmanager_receivers"]`. Collect SHALL persist `receiver_names` only and SHALL NOT persist decoded Alertmanager YAML or webhook URLs. Missing collect or `_hc_error` SHALL be SKIPPED. Names `null`, `Default`, `default`, `Watchdog`, and `watchdog` SHALL be ignored. Zero names remaining after that ignore list SHALL be FAIL. Else PASS. The engine SHALL NOT score AlertmanagerConfig custom resources.

#### Scenario: empty receiver_names is FAIL
- GIVEN redacted collect with `receiver_names` `[]`
- WHEN evaluate_checks core
- THEN `7.6.alert_receivers` is FAIL

#### Scenario: ignored-only names is FAIL
- GIVEN names `["null"]`
- WHEN evaluate_checks core
- THEN `7.6.alert_receivers` is FAIL

#### Scenario: a real receiver name is PASS
- GIVEN names `["pagerduty-prod"]`
- WHEN evaluate_checks core
- THEN `7.6.alert_receivers` is PASS

#### Scenario: collection error is SKIPPED
- GIVEN `_hc_error`
- WHEN evaluate_checks core
- THEN `7.6.alert_receivers` is SKIPPED

### Requirement: Sparse TSR alias for alert receivers
KB row `7.6.tsr.6_3_2_alert_receivers` SHALL be a sparse alias (`content_from` exact `7.6.alert_receivers`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: alert receivers TSR aliases native
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_3_2_alert_receivers` is loaded
- THEN `content_from` is `7.6.alert_receivers`

## MODIFIED Requirements

None. `7.6.update_impact` and `7.6.remote_health` SKIPPED stubs are unchanged.
