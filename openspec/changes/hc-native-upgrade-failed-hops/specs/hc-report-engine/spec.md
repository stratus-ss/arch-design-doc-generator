# Health Check Report Engine (`hc-native-upgrade-failed-hops` delta)

## ADDED Requirements

### Requirement: Native ClusterVersion failed or partial hops
Core evaluation SHALL emit `7.6.upgrade.failed_hops` with title `ClusterVersion failed or partial hops`. `_hc_error` SHALL be SKIPPED. Missing or `_hc_not_found` SHALL be NOT_APPLICABLE. Empty `status.history` SHALL be NOT_APPLICABLE. Any history item whose `state` is `Partial` or `Failed` (case-sensitive) SHALL be FAIL. Else when history is present the status SHALL be PASS. The check SHALL never emit WARNING. `7.6.upgrade.history` Completed-only bars SHALL not change in this change.

#### Scenario: Partial hop fails
- GIVEN ClusterVersion history containing a hop with `state` `Partial`
- WHEN core evaluation runs
- THEN `7.6.upgrade.failed_hops` status is FAIL
- AND the status is not PASS

#### Scenario: all Completed hops pass
- GIVEN ClusterVersion history whose hops are all `Completed`
- WHEN core evaluation runs
- THEN `7.6.upgrade.failed_hops` status is PASS
- AND the status is not FAIL

#### Scenario: collection error is skipped
- GIVEN clusterversion payload with `_hc_error`
- WHEN core evaluation runs
- THEN `7.6.upgrade.failed_hops` status is SKIPPED
- AND the status is not FAIL

### Requirement: Update-history TSR stays on Completed native
KB row `7.6.tsr.6_2_1_update_history` SHALL remain a sparse alias (`content_from` exact `7.6.upgrade.history`). It SHALL NOT use `content_from` `7.6.upgrade.failed_hops`.

#### Scenario: update history TSR is not retargeted
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_2_1_update_history` is loaded
- THEN `content_from` is `7.6.upgrade.history`
- AND `content_from` is not `7.6.upgrade.failed_hops`

## MODIFIED Requirements

None.
