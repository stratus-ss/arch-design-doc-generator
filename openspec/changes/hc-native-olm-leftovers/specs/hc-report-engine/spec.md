# Health Check Report Engine (`hc-native-olm-leftovers` delta)

## ADDED Requirements

### Requirement: Native OLM failed CSV scoring
Core evaluation SHALL emit `7.3.olm.failed_csv` with title `OLM failed ClusterServiceVersions`. `_hc_error` SHALL be SKIPPED. Missing payload SHALL be NOT_APPLICABLE. Zero ClusterServiceVersion items SHALL be NOT_APPLICABLE. Any item with `status.phase` equal to `Failed` SHALL be FAIL. Else any item whose phase is neither `Succeeded` nor empty SHALL be WARNING. Else PASS. Succeeded copied CSVs SHALL NOT FAIL or WARNING. `7.3.co.platform` scoring SHALL not change in this change.

#### Scenario: Failed CSV is FAIL
- GIVEN a ClusterServiceVersion with `status.phase` `Failed`
- WHEN core evaluation runs
- THEN `7.3.olm.failed_csv` status is FAIL

#### Scenario: Succeeded CSV is PASS
- GIVEN only ClusterServiceVersions with `status.phase` `Succeeded`
- WHEN core evaluation runs
- THEN `7.3.olm.failed_csv` status is PASS
- AND the status is not FAIL

#### Scenario: Replacing CSV is WARNING
- GIVEN a ClusterServiceVersion with `status.phase` `Replacing`
- AND no Failed phase
- WHEN core evaluation runs
- THEN `7.3.olm.failed_csv` status is WARNING

### Requirement: Additional operators TSR stays on platform rollup
KB row `7.3.tsr.3_2_2_additional_operators` SHALL keep `content_from` exact `7.3.co.platform`. This change SHALL NOT retarget that row onto `7.3.olm.failed_csv`. Insights `7.7.ccx_internal.uninstalled_operators_with_leftover_resources` SHALL NOT receive `content_from` from this native.

#### Scenario: additional operators TSR remains on co.platform
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_2_2_additional_operators` is loaded
- THEN `content_from` is `7.3.co.platform`
