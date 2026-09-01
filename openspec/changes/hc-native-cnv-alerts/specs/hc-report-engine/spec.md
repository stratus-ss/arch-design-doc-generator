# Health Check Report Engine (`hc-native-cnv-alerts` delta)

## ADDED Requirements

### Requirement: Native CNV firing-alert scoring
Core evaluation SHALL emit `7.4.cnv.alerts`. The engine SHALL read `results["07_cluster_health"]["firing_alerts"]`. Missing `firing_alerts` (`_is_missing`) SHALL be SKIPPED. The engine SHALL parse the list via `_parse_alerts_list`. A virt-matching alert SHALL be one whose `alertname` or `namespace` (casefold) contains any of `kubevirt`, `cdi`, `ssp`, `hco`, `hyperconverged`, `openshift-cnv`, `nmstate`. Alerts whose `state` is not `firing` or `pending` (casefold) SHALL be ignored. Any remaining virt-matching alert SHALL be FAIL. Else the check SHALL PASS. The check SHALL NEVER be WARNING. The engine SHALL NOT retune `7.5.alerts.critical`. Collect SHALL NOT add a new firing-alerts command. Prometheus SHALL NOT be queried again for this check.

#### Scenario: kubevirt firing is FAIL
- GIVEN a firing alert whose alertname contains `KubeVirt`
- WHEN evaluate_checks core
- THEN `7.4.cnv.alerts` is FAIL

#### Scenario: platform-only alerts is PASS
- GIVEN a firing alert `CPUThrottlingHigh` with no virt token in name or namespace
- WHEN evaluate_checks core
- THEN `7.4.cnv.alerts` is PASS

#### Scenario: empty alert list is PASS
- GIVEN `firing_alerts` with an empty `alerts` list
- WHEN evaluate_checks core
- THEN `7.4.cnv.alerts` is PASS

#### Scenario: missing firing_alerts is SKIPPED
- GIVEN missing `firing_alerts`
- WHEN evaluate_checks core
- THEN `7.4.cnv.alerts` is SKIPPED

### Requirement: Sparse TSR alias for CNV active alerts
KB row `7.4.tsr.4_8_5_2_1_active_alerts` SHALL be a sparse alias (`content_from` exact `7.4.cnv.alerts`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: CNV active alerts TSR aliases native
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_5_2_1_active_alerts` is loaded
- THEN `content_from` is `7.4.cnv.alerts`

## MODIFIED Requirements

None. `7.5.alerts.critical` bars are unchanged.
