# Health Check Report Engine (`hc-native-volume-mount` delta)

## ADDED Requirements

### Requirement: Native volume mount p99 scoring
Core evaluation SHALL emit `7.5.volume.mount_p99`. The engine SHALL read `results["10_metrics"]["volume_mount_p99"]`. Missing payload or `_hc_error` SHALL be SKIPPED. A successful query whose result vector is empty SHALL be INFO. The scored value SHALL be the maximum numeric sample in the vector. A maximum greater than 10 seconds SHALL be FAIL. A maximum greater than 2 seconds and at most 10 seconds SHALL be WARNING. Else PASS. The engine SHALL NOT scrape host mount tables. The engine SHALL NOT retune PVC used-percent checks. The engine SHALL NOT emit `7.5.vol_mount`.

#### Scenario: p99 above 10 seconds is FAIL
- GIVEN `volume_mount_p99` has a successful Prometheus vector
- AND the maximum sample is greater than 10 seconds
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is FAIL

#### Scenario: p99 above 2 seconds is WARNING
- GIVEN `volume_mount_p99` has a successful Prometheus vector
- AND the maximum sample is greater than 2 seconds and at most 10 seconds
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is WARNING

#### Scenario: p99 at or below 2 seconds is PASS
- GIVEN `volume_mount_p99` has a successful Prometheus vector
- AND the maximum sample is at most 2 seconds
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is PASS

#### Scenario: empty result vector is INFO
- GIVEN `volume_mount_p99` is present and not `_hc_error`
- AND the Prometheus result vector is empty
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is INFO
- AND the status is not FAIL

#### Scenario: missing query is SKIPPED
- GIVEN `volume_mount_p99` is missing or `_hc_error`
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is SKIPPED

### Requirement: TSR 5.10 aliases the native
KB row `7.5.tsr.5_10_volume_mount_durations` SHALL set `content_from` exact `7.5.volume.mount_p99`. The row SHALL set `include_in_findings` false.

#### Scenario: TSR 5.10 aliases native mount p99
- GIVEN production `load_kb()`
- WHEN entry `7.5.tsr.5_10_volume_mount_durations` is loaded
- THEN `content_from` is `7.5.volume.mount_p99`
- AND `include_in_findings` is false

## MODIFIED Requirements

None. PVC used-percent scoring is unchanged.
