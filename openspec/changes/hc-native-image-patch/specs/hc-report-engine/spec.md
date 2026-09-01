# Health Check Report Engine (`hc-native-image-patch` delta)

## ADDED Requirements

### Requirement: Native image registrySources scoring
Core evaluation SHALL emit `7.6.image.registry_sources` with title `Image registry sources`. `_hc_error` SHALL be SKIPPED. Missing or `_hc_not_found` SHALL be NOT_APPLICABLE. The engine SHALL read `spec.registrySources` and treat a missing object as empty lists. Allowed, blocked, and insecure values that are not lists SHALL be treated as empty. Allowed and blocked both non-empty SHALL be FAIL. Else insecure non-empty SHALL be WARNING. Else allowed empty and blocked empty SHALL be INFO. Else PASS (allow-only or block-only, no insecure). Empty connected-cluster defaults SHALL NOT FAIL. `7.6.image_mgmt` bars SHALL not change in this change.

#### Scenario: empty allow and block is INFO
- GIVEN `registrySources` with empty allowed, blocked, and insecure lists
- WHEN core evaluation runs
- THEN `7.6.image.registry_sources` status is INFO
- AND the status is not WARNING or FAIL

#### Scenario: insecure registries is WARNING
- GIVEN a non-empty `insecureRegistries` list
- AND allowed and blocked are not both non-empty
- WHEN core evaluation runs
- THEN `7.6.image.registry_sources` status is WARNING
- AND the status is not PASS

#### Scenario: allowed and blocked together fails
- GIVEN non-empty `allowedRegistries` and non-empty `blockedRegistries`
- WHEN core evaluation runs
- THEN `7.6.image.registry_sources` status is FAIL

### Requirement: Sparse TSR alias for images patch management
KB row `7.6.tsr.6_2_3_images_patch_management` SHALL be a sparse alias (`content_from` exact `7.6.image.registry_sources`, `include_in_findings = false`). It SHALL NOT target `7.6.image_mgmt`. Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: image TSR aliases 7.6.image.registry_sources
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_2_3_images_patch_management` is loaded
- THEN `content_from` is `7.6.image.registry_sources`
- AND `include_in_findings` is false

## MODIFIED Requirements

### Requirement: Wrong-story TSR rows stay canonical
This requirement is replaced for the image leaf. `7.6.tsr.6_2_3_images_patch_management` SHALL alias `7.6.image.registry_sources`.

#### Scenario: image TSR is not an alias
This scenario is withdrawn. Image TSR SHALL alias `7.6.image.registry_sources` and SHALL NOT alias `7.6.image_mgmt`.
