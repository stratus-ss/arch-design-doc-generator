# Health Check Report Engine (`hc-native-netpol-prune` delta)

## ADDED Requirements

### Requirement: Collect NetworkPolicy lists
Live and supportshell collect SHALL write `networkpolicy` under `08_day2` via `oc get networkpolicy -A`.

#### Scenario: networkpolicy capture name exists
- GIVEN live `08_day2.sh`
- WHEN an operator inspects capture stems
- THEN `networkpolicy` is present as a capture name

### Requirement: Native orphan NetworkPolicy scoring
Core evaluation SHALL emit `7.6.netpol.orphan` with title `Orphan user NetworkPolicies`. Missing or `_hc_error` networkpolicy payload SHALL be SKIPPED. Zero user-namespace policies SHALL be INFO. User namespaces SHALL skip `openshift-*`, `kube-*`, `default`, and `openshift`. A policy whose `podSelector` is missing or whose `matchLabels` is empty or missing and that has no `matchExpressions` SHALL NOT be an orphan. A policy with `matchExpressions` and no `matchLabels` SHALL be skipped. For a non-empty `matchLabels` dict, the engine SHALL count pods in that namespace whose phase is not Succeeded or Failed and whose labels contain every key/value. Count 0 SHALL be an orphan. Any orphan SHALL be FAIL. Else PASS. `7.6.prune.netpol` SHALL remain SKIPPED.

#### Scenario: labeled selector matching zero pods fails
- GIVEN a user NetworkPolicy with `matchLabels` that match zero non-terminal pods in that namespace
- WHEN core evaluation runs
- THEN `7.6.netpol.orphan` status is FAIL

#### Scenario: empty selector is not an orphan
- GIVEN user NetworkPolicies exist
- AND every user policy has an empty `podSelector` with no `matchLabels`
- WHEN core evaluation runs
- THEN `7.6.netpol.orphan` status is PASS
- AND the status is not FAIL

#### Scenario: no user policies is INFO
- GIVEN NetworkPolicy items exist only in platform namespaces, or the user-namespace list is empty
- WHEN core evaluation runs
- THEN `7.6.netpol.orphan` status is INFO
- AND the status is not FAIL

### Requirement: Sparse TSR alias for network policy pruning
KB row `7.6.tsr.6_1_5_3_network_policy_pruning` SHALL be a sparse alias (`content_from` exact `7.6.netpol.orphan`, `include_in_findings = false`). It SHALL NOT target `7.6.prune.netpol`. Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: netpol TSR aliases 7.6.netpol.orphan
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_5_3_network_policy_pruning` is loaded
- THEN `content_from` is `7.6.netpol.orphan`
- AND `include_in_findings` is false

## MODIFIED Requirements

### Requirement: Wrong-story TSR rows stay canonical
This requirement is replaced for the netpol leaf. `7.6.tsr.6_1_5_3_network_policy_pruning` SHALL alias `7.6.netpol.orphan`.

#### Scenario: netpol TSR is not an alias
This scenario is withdrawn. Netpol TSR SHALL alias `7.6.netpol.orphan` and SHALL NOT alias `7.6.prune.netpol`.
