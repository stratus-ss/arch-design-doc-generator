# Health Check Report Engine (`hc-native-quay-pods` delta)

## ADDED Requirements

### Requirement: Native Quay application pod scoring
Core evaluation SHALL emit `7.4.quay.pods` with title `Internal Quay application pods`. The engine SHALL read `results["06_layered"]["quay_registry"]` and `results["06_layered"]["quay_pods"]`. Registry namespaces SHALL be the unique `metadata.namespace` of each QuayRegistry item plus `spec.targetNamespace` when present. A matching application pod SHALL be a pod whose `metadata.name` contains `quay-app` or `registry-quay-app`. Running SHALL mean `status.phase` is `Running` and every `containerStatuses` entry has `ready` true. Missing or `_hc_error` `quay_pods` SHALL be SKIPPED. Zero QuayRegistry items SHALL be NOT_APPLICABLE. Any registry namespace with zero matching Running pods SHALL be FAIL. Else PASS. The engine SHALL NOT score QuayRegistry Available as a substitute. The engine SHALL NOT retune `_evaluate_layered_product` for Quay Registry.

#### Scenario: no QuayRegistry is NOT_APPLICABLE
- GIVEN `quay_registry` has no items or `_hc_not_found`
- AND `quay_pods` is present and not `_hc_error`
- WHEN core evaluation runs
- THEN `7.4.quay.pods` status is NOT_APPLICABLE

#### Scenario: installed registry without app pod is FAIL
- GIVEN at least one QuayRegistry
- AND that registry's namespace has no Running matching application pod
- WHEN core evaluation runs
- THEN `7.4.quay.pods` status is FAIL

#### Scenario: Running quay-app pod is PASS
- GIVEN at least one QuayRegistry
- AND every registry namespace has at least one matching Running application pod
- WHEN core evaluation runs
- THEN `7.4.quay.pods` status is PASS

#### Scenario: missing quay_pods is SKIPPED
- GIVEN `quay_pods` is missing or `_hc_error`
- WHEN core evaluation runs
- THEN `7.4.quay.pods` status is SKIPPED

### Requirement: TSR Quay pod leaves alias the native
KB rows `7.4.tsr.4_5_2_quay_pods` and `7.4.tsr.4_5_4_1_quay_pods` SHALL use `content_from` exact `7.4.quay.pods` and `include_in_findings = false`. The engine SHALL NOT add or retarget `7.4.tsr.4_5_1_1_quay_supported_configuration`.

#### Scenario: pod TSR aliases native
- GIVEN production `load_kb()`
- WHEN entries `7.4.tsr.4_5_2_quay_pods` and `7.4.tsr.4_5_4_1_quay_pods` are loaded
- THEN each `content_from` is `7.4.quay.pods`
- AND each `include_in_findings` is false

## MODIFIED Requirements

None. Quay Registry product inventory scoring is unchanged.
