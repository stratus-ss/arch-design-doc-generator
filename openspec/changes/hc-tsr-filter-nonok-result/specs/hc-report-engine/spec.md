# Health Check Report Engine (`hc-tsr-filter-nonok-result` delta)

## MODIFIED Requirements

### Requirement: TSR Result length
After HTML strip: unfiltered Status (PASS, INFO, SKIPPED, NOT_APPLICABLE) condenses then clips at 32_000. FAIL/WARNING keep-important-lines, then node/pod condense, then clip.

#### Scenario: Text past 2000 characters is kept
- GIVEN check Status PASS and Result over 2000 characters under 32_000
- WHEN parsed
- THEN characters after offset 2000 remain

### Requirement: TSR identical pass-host condensation
Applies only on the unfiltered Status path.

#### Scenario: Mixed WARNING Result omits PASS NODES
- GIVEN check Status WARNING and mixed PASS/WARNING hosts
- WHEN parsed
- THEN no PASS NODES, no ALL NODES, non-ok hostname remains

## ADDED Requirements

### Requirement: TSR FAIL/WARNING Result line filter
FAIL/WARNING Results keep `[FAIL]`/`[WARNING]`/`[WARN]`/`[LIMITATION]`/`[SUPPORT LIMITATION]` plus wrappers with kept children. Drop PASS/INFO/SKIP/NA and inventory. No ALL NODES/PASS NODES. CCX unchanged.

#### Scenario: WARNING Result keeps only important lines
- GIVEN mixed tokens and a ` · ` table on Status WARNING
- WHEN parsed
- THEN LIMITATION/WARNING remain; PASS/INFO/SKIP/NA and inventory names are absent

#### Scenario: Unfiltered Status keeps PASS and INFO lines
- GIVEN `[PASS]` and `[INFO]` lines
- WHEN Status is PASS or NOT_APPLICABLE
- THEN both tokens remain in evidence
