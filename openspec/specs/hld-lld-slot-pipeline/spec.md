# HLD/LLD Slot Pipeline

> **Canonical spec:** this file (`openspec/specs/hld-lld-slot-pipeline/spec.md`). Do not recreate `agent_planning/openspec/specs/`.

## Purpose

One ADR extraction produces one `slot_map.json` that renders both HLD and LLD from generic public templates. Shell `${VAR}` sequences are not substituted. Empty slots render `{TBD}`. Setup refuses to overwrite existing working copies unless `--force`. Public templates contain no client PII. `IMAGE_REGISTRY` and `REGISTRY_MIRROR` remain distinct unless `registry_mirror_policy: same_as_image_registry` copies the image registry into an empty mirror. Prompt A defaults to one full-ADR chunk with an automatic chunked fallback. Prompt B is opt-in. Operator overlay and empty-required repair bind facts the extract missed. Stampable `.drawio` files use the same `{TOKEN}` engine.

## Requirements

### Requirement: Unified slot map
The system SHALL render HLD and LLD from a single `slot_map.json` and SHALL NOT run a second LLD-only AI extract.

#### Scenario: One map fills both document types
- GIVEN a valid `slot_map.json` produced by the HLD extract pipeline
- WHEN HLD markdown and LLD markdown are rendered
- THEN both use that same map
- AND no second LLD-only extract is invoked

### Requirement: Shell-safe placeholders
Placeholder matching SHALL NOT treat `{TOKEN}` as a slot when immediately preceded by `$`.

#### Scenario: Dollar-prefixed braces survive render
- GIVEN template text containing `{CLIENT}` and `${CLUSTER}`
- WHEN the slot renderer runs
- THEN `{CLIENT}` is substituted
- AND `${CLUSTER}` is unchanged

### Requirement: Empty values render TBD
Empty unprefixed slots SHALL render as `{TBD}`.

#### Scenario: Blank slot becomes TBD
- GIVEN a slot key present in the template whose value is empty
- WHEN the slot renderer runs
- THEN the output contains `{TBD}` for that token

### Requirement: Setup fail-closed overwrite
Setup without `--force` SHALL exit non-zero when destination working copies exist. `--force` SHALL overwrite. First-time setup SHALL copy without `--force`.

#### Scenario: Existing working copies block setup
- GIVEN destination HLD or LLD working copies already exist
- WHEN setup runs without `--force`
- THEN the process exits non-zero
- AND the warning names `--force`

### Requirement: Generic public templates
Public templates SHALL contain no client proper names (`NFCU`, `Steve Ovens`).

#### Scenario: Templates stay generic
- GIVEN files under `templates/`
- WHEN a client-name scan for `NFCU` or `Steve Ovens` runs
- THEN there are no matches in public templates

#### Scenario: Templates contain no engagement person or site names
- GIVEN files under `templates/`
- WHEN a scan for `Brian Ong`, `Pedro Moreno`, `Monte`, `Fairview` runs
- THEN there are no matches under `templates/`

### Requirement: Sanitize diagrams default is in-place
Default sanitize SHALL not copy `output/Diagrams` into `templates/` without `--yes`.

#### Scenario: From-output copy requires confirmation
- GIVEN `output/Diagrams/phase*` drawio files exist
- WHEN sanitize runs with `--from-output` and without `--yes`
- THEN it prints planned writes
- AND it writes nothing under `templates/`
- AND it exits 2

### Requirement: Work-item phases key by yaml id
Work-item `--phases N` SHALL select yaml id `phaseN`, not list index N.

#### Scenario: Integer phase token maps to yaml id
- GIVEN `project.yaml` phases include `phase1-hub` before `phase4`
- WHEN work-items runs with `--phases 4`
- THEN it selects yaml id `phaseN` for N=4
- AND it does not select the 4th list entry by enumerate index

### Requirement: Distinct registry facts
`IMAGE_REGISTRY` and `REGISTRY_MIRROR` SHALL remain independent keys except when `registry_mirror_policy` explicitly copies.

#### Scenario: Default keeps registry keys independent
- GIVEN `registry_mirror_policy` is `unset` or `distinct`
- WHEN extract fills `IMAGE_REGISTRY` and leaves `REGISTRY_MIRROR` empty
- THEN `REGISTRY_MIRROR` is not silently set to `IMAGE_REGISTRY`

### Requirement: Single-pass Prompt A
Default Prompt A SHALL use one chunk containing the full ADR text.

#### Scenario: One chunk includes the ADR tail
- GIVEN an ADR whose tail sits beyond 12 000 characters
- WHEN Prompt A runs with default `adr_mode=auto`
- THEN the extractor builds exactly one chunk
- AND that chunk text includes the ADR tail

### Requirement: Chunked fallback
On Prompt A timeout or JSON parse failure, the system SHALL retry once with 8×12k chunking and SHALL record `adr_mode_used`.

#### Scenario: Timeout or parse failure retries chunked
- GIVEN default `adr_mode=auto`
- AND the single-pass Prompt A times out or returns unparseable JSON
- WHEN the extractor recovers
- THEN it retries Prompt A once with `max_chars=12000` and `max_chunks=8`
- AND `adr_mode_used` is recorded as `chunked`

### Requirement: Forced chunked mode
`--adr-mode chunked` SHALL NOT attempt single-pass.

#### Scenario: Flag skips single-pass
- GIVEN `--adr-mode chunked`
- WHEN Prompt A runs
- THEN chunks are built with 8×12k limits
- AND no full-ADR single chunk is attempted first

### Requirement: Prompt B opt-in
Prompt B (per-phase refine) SHALL NOT run unless `--refine-phases` or `REFINE_PHASES=1`.

#### Scenario: Default skips phase refine
- GIVEN `prepare-hld-ai` with no `REFINE_PHASES`
- WHEN extraction runs
- THEN Prompt B is not invoked
- AND Prompt B code remains available for opt-in

### Requirement: Overlay nonempty override
A non-empty `project.yaml` `slots:` value SHALL override the extract value for that key.

#### Scenario: Overlay wins over extract
- GIVEN extract `CLIENT_DOMAIN` is `extracted.example`
- AND `project.yaml` `slots.CLIENT_DOMAIN` is `overlay.example`
- WHEN overlay is applied
- THEN `CLIENT_DOMAIN` is `overlay.example`

### Requirement: Overlay empty does not wipe
An empty or omitted overlay key SHALL NOT wipe a filled extract value.

#### Scenario: Empty overlay leaves extract
- GIVEN extract `GITOPS_HOST` is `git.example`
- AND `project.yaml` `slots.GITOPS_HOST` is `""` or omitted
- WHEN overlay is applied
- THEN `GITOPS_HOST` remains `git.example`

### Requirement: Registry mirror policy copy
When `registry_mirror_policy` is `same_as_image_registry` and `REGISTRY_MIRROR` is empty, the system SHALL copy `IMAGE_REGISTRY` into `REGISTRY_MIRROR`.

#### Scenario: Policy copies image registry into empty mirror
- GIVEN `IMAGE_REGISTRY` is non-empty
- AND `REGISTRY_MIRROR` is empty
- AND `registry_mirror_policy` is `same_as_image_registry`
- WHEN overlay policy is applied
- THEN `REGISTRY_MIRROR` equals `IMAGE_REGISTRY`

### Requirement: Empty-required repair skip
Empty-required repair SHALL be skipped when no required slot is blank.

#### Scenario: No model call when required slots are filled
- GIVEN every schema-required slot has a non-blank value
- WHEN the empty-repair stage runs
- THEN the model is not invoked
- AND the run logs that repair was skipped

### Requirement: Drawio slot stamp
Drawio `{TOKEN}` SHALL fill; `${TOKEN}` SHALL NOT.

#### Scenario: Drawio respects dollar lookbehind
- GIVEN drawio XML containing `{ITSM_PLATFORM}` and `${FOO}`
- WHEN drawio render runs with a filled `ITSM_PLATFORM`
- THEN `{ITSM_PLATFORM}` is replaced with the slot value
- AND `${FOO}` is unchanged

### Requirement: Fingerprint skip still binds
A fingerprint-fresh run SHALL apply overlay and render diagrams without re-calling Prompt A.

#### Scenario: Cached extract still overlays and stamps
- GIVEN an unchanged ADR, schema, prompts, and `adr_mode` fingerprint
- WHEN `prepare-hld-ai` runs without `FORCE=1`
- THEN Prompt A is not re-invoked
- AND yaml overlay still applies
- AND markdown and drawio render still run
