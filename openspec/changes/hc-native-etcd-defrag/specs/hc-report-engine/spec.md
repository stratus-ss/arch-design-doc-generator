# Health Check Report Engine (`hc-native-etcd-defrag` delta)

## ADDED Requirements

### Requirement: Native etcd fragment-ratio rollup
Core evaluation SHALL emit `7.8.etcd.defrag`. The engine SHALL read Prometheus vectors `etcd_db_size_bytes` and `etcd_db_size_in_use`. A member sample SHALL match when both vectors share the same `pod` label. Fragment ratio SHALL be `(size - used) / size` when size is greater than zero. Missing both files SHALL be SKIPPED. Present files with no matching samples SHALL be INFO. Any member ratio greater than or equal to 0.70 SHALL be FAIL. Else any member ratio greater than or equal to 0.50 SHALL be WARNING. Else PASS. The engine SHALL NOT retune `7.8.etcd.db.*` 4GiB or 8GiB bars. The engine SHALL NOT scrape defrag log phrases.

#### Scenario: high fragment ratio is FAIL
- GIVEN at least one matched etcd member whose fragment ratio is 0.70 or higher
- WHEN core evaluation runs
- THEN `7.8.etcd.defrag` status is FAIL

#### Scenario: mid fragment ratio is WARNING
- GIVEN at least one matched member whose fragment ratio is 0.50 or higher
- AND no member ratio is 0.70 or higher
- WHEN core evaluation runs
- THEN `7.8.etcd.defrag` status is WARNING

#### Scenario: low fragment ratio is PASS
- GIVEN every matched member fragment ratio is below 0.50
- WHEN core evaluation runs
- THEN `7.8.etcd.defrag` status is PASS

#### Scenario: empty samples are INFO
- GIVEN both files are present
- AND there are no matching size and in-use samples
- WHEN core evaluation runs
- THEN `7.8.etcd.defrag` status is INFO
- AND the status is not FAIL

#### Scenario: missing both files is SKIPPED
- GIVEN both `etcd_db_size_bytes` and `etcd_db_size_in_use` are missing
- WHEN core evaluation runs
- THEN `7.8.etcd.defrag` status is SKIPPED

### Requirement: TSR defragmentation aliases native defrag
KB row `7.3.tsr.3_5_6_etcd_defragmentation` SHALL use `content_from` exact `7.8.etcd.defrag` and `include_in_findings` false. The alias SHALL NOT keep inherited description, recommendation, verification, or links.

#### Scenario: TSR 3.5.6 aliases native defrag
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_5_6_etcd_defragmentation` is loaded
- THEN `content_from` is `7.8.etcd.defrag`
- AND `include_in_findings` is false

## MODIFIED Requirements

None. Per-member etcd DB size scoring is unchanged.
