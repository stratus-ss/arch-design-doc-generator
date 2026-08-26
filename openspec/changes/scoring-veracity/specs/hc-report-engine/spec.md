# Health Check Report Engine (`scoring-veracity` delta)

## MODIFIED Requirements

### Requirement: CheckResult and Finding fields
Cross-module objects SHALL keep the `CheckResult` and `Finding` field names used by evaluators, findings, renderer, and audit JSON.

#### Scenario: CheckResult scoring_basis vocabulary
- GIVEN a `CheckResult`
- WHEN it is stored
- THEN `scoring_basis` is `doc_backed`, `engine_policy`, or empty

#### Scenario: Audit JSON includes scoring_basis
- GIVEN generate writes audit JSON
- WHEN a check is serialized
- THEN `checks[].scoring_basis` is present

## ADDED Requirements

### Requirement: Chapter 7 scoring provenance
Chapter 7 SHALL show a Scoring row only for FAIL and WARNING.

#### Scenario: FAIL or WARNING shows Scoring
- GIVEN a check with status FAIL or WARNING
- WHEN Chapter 7 is rendered
- THEN the table includes a Scoring row
- AND the cell is `Doc-backed` when `scoring_basis` is `doc_backed`
- AND the cell is `Engine policy` otherwise

#### Scenario: Other statuses omit Scoring
- GIVEN a check with status PASS, INFO, SKIPPED, or NOT_APPLICABLE
- WHEN Chapter 7 is rendered
- THEN there is no Scoring row

### Requirement: mastersSchedulable native scoring
Native `7.1.nodes.master_sched` SHALL follow topology and the Scheduler flag.

#### Scenario: Missing scheduler
- GIVEN the Scheduler object is missing
- WHEN the check runs
- THEN status is SKIPPED

#### Scenario: Dedicated control plane schedulable
- GIVEN a non-compact cluster and `mastersSchedulable` true
- WHEN the check runs
- THEN status is WARNING
- AND `scoring_basis` is `doc_backed`

#### Scenario: Dedicated control plane not schedulable
- GIVEN a non-compact cluster and `mastersSchedulable` false
- WHEN the check runs
- THEN status is PASS
- AND `scoring_basis` is `doc_backed`

#### Scenario: Compact or SNO schedulable
- GIVEN `is_compact_cluster` is true and `mastersSchedulable` true
- WHEN the check runs
- THEN status is INFO

#### Scenario: Compact or SNO not schedulable
- GIVEN `is_compact_cluster` is true and `mastersSchedulable` false
- WHEN the check runs
- THEN status is WARNING
- AND `scoring_basis` is `doc_backed`

### Requirement: FIPS native scoring
Native `7.1.sys.fips` SHALL not PASS when FIPS is off.

#### Scenario: FIPS disabled
- GIVEN install-config does not match `fips: true`
- WHEN the check runs
- THEN status is INFO

#### Scenario: FIPS enabled
- GIVEN install-config matches `fips: true`
- WHEN the check runs
- THEN status is PASS

### Requirement: FeatureGate native scoring
Native `7.3.net.featuregates` SHALL not claim TechPreview absence from clusteroperators.

#### Scenario: FeatureGate not collected
- GIVEN FeatureGate is not in the collection
- WHEN the check runs
- THEN status is SKIPPED

### Requirement: Virtualization Automatic approval
Shared approval evaluation SHALL not WARNING solely for OpenShift Virtualization Automatic approval.

#### Scenario: Only kubevirt-hyperconverged is Automatic
- GIVEN the only Automatic subscription is `kubevirt-hyperconverged` by `metadata.name` or `spec.name`
- WHEN `_evaluate_approval_strategy` runs
- THEN status is PASS

#### Scenario: Other Automatic subscriptions
- GIVEN a non-virtualization subscription uses Automatic
- WHEN `_evaluate_approval_strategy` runs
- THEN status is WARNING
- AND `scoring_basis` is `engine_policy`

### Requirement: Documented install minimums
Below documented CPU, memory, or disk floors SHALL be FAIL in 7.1 aggregate node checks and 7.2 per-node checks.

#### Scenario: Below floor is FAIL
- GIVEN a node is below `_MASTER_MIN_CPU`, `_MASTER_MIN_MEM_GIB`, `_WORKER_MIN_CPU`, `_WORKER_MIN_MEM_GIB`, or `_MIN_DISK_GIB` as applicable
- WHEN the matching 7.1 or 7.2 check runs
- THEN status is FAIL
- AND `scoring_basis` is `doc_backed`

### Requirement: etcd WAL and backend native scoring
WAL P99 SHALL use the documented 10 ms FAIL bar. Backend commit SHALL not FAIL or WARNING from undocumented 25/50 ms bands.

#### Scenario: WAL above 10 ms
- GIVEN WAL fsync P99 is greater than 10 milliseconds
- WHEN the check runs
- THEN status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: WAL at or below 10 ms
- GIVEN WAL fsync P99 is at most 10 milliseconds
- WHEN the check runs
- THEN status is PASS

#### Scenario: Backend commit high
- GIVEN backend commit P99 is greater than 25 milliseconds
- WHEN the check runs
- THEN status is INFO
- AND Chapter 6 has no finding from this INFO unless `finding_on_info` is set

#### Scenario: Backend commit healthy
- GIVEN backend commit P99 is at most 25 milliseconds
- WHEN the check runs
- THEN status is PASS

### Requirement: No native 7.3 etcd metric placeholders
Native Chapter 7 SHALL not emit SKIPPED placeholder rows for TSR 3.5.4–3.5.9 etcd metric theater.

#### Scenario: Placeholders absent
- GIVEN standard collection without etcdctl prometheus placeholders
- WHEN 7.3 etcd native evaluation runs
- THEN check IDs for sections 3.5.4 through 3.5.9 placeholders are not emitted
