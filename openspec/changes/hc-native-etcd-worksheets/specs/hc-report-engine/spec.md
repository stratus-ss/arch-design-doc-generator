# Health Check Report Engine (`hc-native-etcd-worksheets` delta)

## ADDED Requirements

### Requirement: Native etcd disk aggregate
Core evaluation SHALL emit `7.8.etcd.disk`. The check SHALL FAIL when any parsed member WAL fsync P99 is greater than 10 milliseconds. The check SHALL PASS when every member with samples is at or below 10 milliseconds. The check SHALL be INFO when there are no WAL samples. Per-pod `7.8.etcd.wal.<pod>` scoring SHALL remain unchanged. `scoring_basis` SHALL be `doc_backed` on disk FAIL.

#### Scenario: any member over the WAL bar
- GIVEN a WAL PromQL vector where at least one member P99 is greater than 10 milliseconds
- WHEN core evaluation runs
- THEN `7.8.etcd.disk` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: all members at or below the WAL bar
- GIVEN a WAL PromQL vector where every member P99 is at most 10 milliseconds
- WHEN core evaluation runs
- THEN `7.8.etcd.disk` status is PASS

#### Scenario: no WAL samples
- GIVEN WAL payload with no usable samples
- WHEN core evaluation runs
- THEN `7.8.etcd.disk` status is INFO

### Requirement: Native etcd compaction scoring
Core evaluation SHALL emit `7.8.etcd.compaction`. FAIL when any pod compaction p95 is greater than 900 milliseconds. WARNING when any pod p95 is greater than 200 milliseconds and at most 900 milliseconds. PASS when all p95 values are at most 200 milliseconds. INFO when the metric is missing or NaN. `scoring_basis` SHALL be `doc_backed` on compaction FAIL. Evidence MAY include auto-compaction flags scanned from collected `etcd_pods` spec. Collect SHALL NOT run etcdctl compact.

#### Scenario: compaction p95 over 900 ms
- GIVEN compaction PromQL with a pod p95 greater than 900 milliseconds
- WHEN core evaluation runs
- THEN `7.8.etcd.compaction` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: compaction p95 in the warning band
- GIVEN compaction PromQL with a pod p95 greater than 200 milliseconds and at most 900 milliseconds
- AND no pod p95 greater than 900 milliseconds
- WHEN core evaluation runs
- THEN `7.8.etcd.compaction` status is WARNING

#### Scenario: compaction metric missing
- GIVEN compaction PromQL empty, error envelope, or NaN
- WHEN core evaluation runs
- THEN `7.8.etcd.compaction` status is INFO

### Requirement: Native etcd log-phrase errors
Core evaluation SHALL emit `7.8.etcd.log_errors`. FAIL when any of these phrases has a count greater than zero in the last six hours: `failed to send out heartbeat on time`, `request timed out`, `rafthttp: failed to read`. PASS when all three counts are zero. INFO when logs are unreadable or the collect envelope is `_hc_error`.

#### Scenario: rafthttp phrase counted
- GIVEN `etcd_log_phrase_counts` with `rafthttp` equal to 1 for a member
- WHEN core evaluation runs
- THEN `7.8.etcd.log_errors` status is FAIL

#### Scenario: all phrase counts zero
- GIVEN every member heartbeat, timed_out, and rafthttp counts are 0
- WHEN core evaluation runs
- THEN `7.8.etcd.log_errors` status is PASS

#### Scenario: logs unreadable
- GIVEN a member object with `_hc_error` true
- WHEN core evaluation runs
- THEN `7.8.etcd.log_errors` status is INFO

### Requirement: Native etcd heartbeat send failures
Core evaluation SHALL emit `7.8.etcd.heartbeat`. WARNING when the sum of one-hour `increase(etcd_server_heartbeat_send_failures_total)` is greater than zero. PASS when the increase is zero. INFO when the metric is missing.

#### Scenario: heartbeat increase positive
- GIVEN heartbeat PromQL increase over one hour greater than zero
- WHEN core evaluation runs
- THEN `7.8.etcd.heartbeat` status is WARNING

#### Scenario: heartbeat increase zero
- GIVEN heartbeat PromQL increase over one hour equal to zero
- WHEN core evaluation runs
- THEN `7.8.etcd.heartbeat` status is PASS

### Requirement: Sparse TSR aliases for ORIG etcd stories
KB rows `7.3.tsr.3_5_5_etcd_compaction`, `7.3.tsr.3_5_7_etcd_log_errors`, and `7.3.tsr.3_5_8_1_etcd_disk_performance` SHALL be sparse aliases (`content_from` to the matching native, `include_in_findings = false`). Alias targets SHALL be `7.8.etcd.compaction`, `7.8.etcd.log_errors`, and `7.8.etcd.disk` respectively. Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: disk TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_5_8_1_etcd_disk_performance` is loaded
- THEN `content_from` is `7.8.etcd.disk`
- AND `include_in_findings` is false

### Requirement: Live-only compaction PromQL and log counts
Live collect MAY write `etcd_compaction_p95` and `etcd_log_phrase_counts` under `10_metrics`. Supportshell MAY omit those files. Supportshell SHALL NOT run PromQL or `oc logs` for these artifacts.

#### Scenario: supportshell omits live-only files
- GIVEN supportshell `10_metrics.sh`
- WHEN an operator runs must-gather collect
- THEN `etcd_compaction_p95` and `etcd_log_phrase_counts` are not produced via PromQL or `oc logs`
