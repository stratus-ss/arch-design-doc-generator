# Health Check Report Engine

> **Canonical spec:** this file (`openspec/specs/hc-report-engine/spec.md`). Do not recreate `agent_planning/openspec/specs/`.
>
> **Baseline date:** 2026-08-21 (landed Chunks A–G). Chunk H deltas live in `openspec/changes/hc-feedback-chunk-h/` until archived.

## Purpose

`make hc-report` turns collected OpenShift cluster JSON (and optional TSR HTML / CCX runtime) into a consultant-facing markdown report. The engine evaluates checks, derives P0–P3 findings from a TOML knowledge base, and fills `{SLOT}` placeholders in `templates/Health_Check/Template_HC_Report.md`. AI is excluded from this path.

## Requirements

### Requirement: No AI on the Health Check path
The Health Check CLI SHALL NOT import or invoke the HLD/LLD AI stack.

#### Scenario: CLI source has no AI tokens
- GIVEN `scripts/health_check/hc_report/cli.py`
- WHEN the file is scanned for `ai_invoke`, `prompt_loader`, `invoke_ai`, `load_prompt_template`, or `CURSOR_API_KEY`
- THEN none of those tokens appear

### Requirement: Report CLI and artifacts
`hc_report.cli` SHALL load results, evaluate checks, derive findings, and write markdown plus audit JSON under the output directory.

#### Scenario: Core profile writes markdown and audit
- GIVEN a collected results directory and `--check-profile core`
- WHEN `cli.main()` runs
- THEN it writes a Health Check markdown report
- AND it writes an audit JSON alongside that report

#### Scenario: Public flags stay stable
- GIVEN `parse_args()`
- WHEN the CLI is invoked
- THEN it accepts `--results-dir`, `--output-dir`, `--config`, `--template`, `--exec-summary`, `--check-profile` (`core` | `extended` | `advisory`), `--ccx-baseline-status`, `--catalog-path`, `--tsr-html`, and `--dry-run`
- AND those flag names are not renamed

### Requirement: Template slot names
`render_report` SHALL substitute the named `{SLOT}` tokens from `templates/Health_Check/Template_HC_Report.md` and SHALL NOT rename them.

#### Scenario: Critical-finding slots exist
- GIVEN the Health Check report template
- WHEN it is filled
- THEN `{CRITICAL_FINDINGS_SUMMARY}` is Chapter 4
- AND `{CRITICAL_FINDINGS}` is §6.1
- AND `{FINDINGS_SECTIONS}` is §6.2

### Requirement: CheckResult and Finding fields
Cross-module objects SHALL keep the `CheckResult` and `Finding` field names used by evaluators, findings, renderer, and audit JSON.

#### Scenario: CheckResult status vocabulary
- GIVEN a `CheckResult`
- WHEN it is stored
- THEN `status` is one of `PASS`, `FAIL`, `WARNING`, `INFO`, `NOT_APPLICABLE`, `SKIPPED`
- AND `source` is `deterministic`, `tsr`, or `ccx`

#### Scenario: Finding carries member ids
- GIVEN a grouped finding
- WHEN it is created
- THEN `member_check_ids` lists every grouped `check_id`
- AND `check_id` is the primary (first) member

### Requirement: Knowledge-base lookup
KB lookup SHALL match an exact `check_id` first, then the first glob pattern (`*` wildcard). Missing recommendation SHALL be `[NEEDS REVIEW]`. Missing or empty `impact` SHALL be treated as no impact triple.

#### Scenario: Glob covers fan-out check ids
- GIVEN a KB row with `pattern = true` and `check_id` containing `*`
- WHEN `get_entry` is called with a generated id that matches that glob
- THEN that row is returned

#### Scenario: Empty recommendation is Needs Review
- GIVEN a check whose KB recommendation is missing or blank
- WHEN a finding is derived
- THEN the recommendation is `[NEEDS REVIEW]`
- AND no category-level fallback paragraph is substituted

#### Scenario: Version-gated recommendation
- GIVEN `recommendation_supported_versions` that does not include the requested OCP minor
- WHEN `get_recommendation` runs
- THEN the returned text starts with `[NEEDS REVIEW]`
- AND it still includes the candidate guidance

### Requirement: KB content_from alias
An alias KB row MAY set `content_from` to an exact canonical `check_id`. `load_kb()` SHALL copy inherited content from that target in a single hop and SHALL keep local identity and finding flags on the alias. Overlay, chains, self-references, missing targets, pattern-row pointers, and glob targets SHALL raise `ValueError`.

#### Scenario: Alias inherits content and keeps local title and flags
- GIVEN alias `content_from = "canonical.id"` and omitted inherited keys
- WHEN `load_kb()` runs
- THEN `get_entry(alias)` recommendation, description, impact, and links equal the canonical row
- AND title stays the alias title
- AND `include_in_findings` stays the alias value

#### Scenario: Missing target fails closed
- GIVEN `content_from` target missing from `entries`
- WHEN `load_kb()` runs
- THEN `ValueError`

#### Scenario: Self-reference fails closed
- GIVEN alias `content_from` equals its own `check_id`
- WHEN `load_kb()` runs
- THEN `ValueError`

#### Scenario: Chain fails closed
- GIVEN A→B and B also has `content_from`
- WHEN `load_kb()` runs
- THEN `ValueError` (chain forbidden; this covers cycles)

#### Scenario: Overlay inherited fields fail closed
- GIVEN alias sets a non-empty `recommendation` (or any other inherited field)
- WHEN `load_kb()` runs
- THEN `ValueError`

#### Scenario: Pattern entry pointer fails closed
- GIVEN `pattern = true` and `content_from` set
- WHEN `load_kb()` runs
- THEN `ValueError`

#### Scenario: Glob target fails closed
- GIVEN target is only a glob in `pattern_entries`
- WHEN `load_kb()` runs
- THEN `ValueError`

### Requirement: KB description is mode-neutral
KB `description` SHALL state what the check evaluates and SHALL NOT encode a single cluster's TSR remainder as the only story.

#### Scenario: Monitoring storage names both emptyDir and RWX/file
- GIVEN `7.3.tsr.3_7_2_monitoring_storage_type`
- WHEN its Description and Recommendation are read
- THEN both mention `emptyDir`
- AND both mention RWX or file/block storage
- AND Description does not say the stack "is configured as" a single type

#### Scenario: OADP recommendation covers non-OLM
- GIVEN `7.4.tsr.4_8_5_3_1_oadp_operator`
- WHEN its Recommendation is read
- THEN it mentions CSV/OLM
- AND it mentions a non-OLM path (Helm, manual, or search outside `openshift-adp`)

#### Scenario: Node Disk heading is virt StorageClass
- GIVEN `7.4.tsr.4_8_1_3_4_node_disk`
- WHEN Description is read
- THEN it describes the default virt StorageClass annotation (`is-default-virt-class`)
- AND it does not describe node root-disk fullness as the worksheet meaning

### Requirement: Optional finding flags
`include_in_findings` SHALL default true. `finding_on_info` SHALL default false.

#### Scenario: include_in_findings false omits Chapter 6
- GIVEN `7.3.tsr.3_13_webhooks` and `7.7.ccx_internal.webhooks_check` with `include_in_findings = false`
- WHEN `derive_findings` runs on FAIL rows for those ids
- THEN neither id appears as a finding or member
- AND chapter 7 may still list the checks

#### Scenario: Live validating webhook still finds
- GIVEN `7.3.webhooks.validatingwebhooks` FAIL
- WHEN `derive_findings` runs
- THEN a finding is created for that check_id

#### Scenario: finding_on_info promotes INFO to P3
- GIVEN a non-CCX INFO check whose KB sets `finding_on_info = true`
- WHEN `derive_findings` runs
- THEN a P3 finding is created
- AND keyword P0/P2 lists are not applied to INFO

### Requirement: Finding priority
FAIL without a P0 keyword SHALL be P1. WARNING with a P2 keyword SHALL be P2, otherwise P3. CCX FAIL SHALL be P2. CCX WARNING SHALL be P3.

#### Scenario: Ordinary FAIL is P1
- GIVEN a deterministic FAIL whose description does not match P0 keywords
- WHEN `derive_findings` runs
- THEN priority is P1

### Requirement: Finding grouping
Checks that share a non-empty KB `finding_group` SHALL collapse to one Chapter 4 / §6.2 finding. Chapter 7 SHALL still list every check.

#### Scenario: Logging not-configured is one finding
- GIVEN FAIL rows for `7.4.tsr.4_1_2_logging_storage_type`, `7.4.tsr.4_1_4_logging_pod_status`, and `7.4.tsr.4_1_5_2_loki_health`
- WHEN `derive_findings` runs
- THEN exactly one finding is produced for that group
- AND `member_check_ids` contains all three ids
- AND title is the group's `finding_group_title`

#### Scenario: Forwarders and SCC stay separate
- GIVEN the logging-not-configured trio plus FAIL `7.4.tsr.4_1_6_cluster_log_forwarders` and `7.4.tsr.4_1_8_logging_security_context_constraints`
- WHEN `derive_findings` runs
- THEN forwarders and SCC are their own findings
- AND they are not members of the logging-not-configured group

#### Scenario: Grouped evidence lists Affected names
- GIVEN two WARNING sysreserved checks with `resource_name` `node-a` and `node-b`
- WHEN `derive_findings` runs
- THEN `Finding.description` starts with `Affected:`
- AND it contains both node names
- AND chapter 7 remains per-node

### Requirement: Chapter 4 and §6.1 summary text
Chapter 4 and §6.1 Summary SHALL use KB `summary_patterns` (first `contains` substring match on finding evidence) then the cleaned first FAIL or WARNING reason. They SHALL NOT use KB `description`. Unusable text (`n/a`, `none`, `unknown`, `na`, too short, no letters) SHALL be omitted. Prose SHALL cap at 220 characters, preferring a sentence end then a word boundary.

#### Scenario: Pattern wins over emptyDir KB description
- GIVEN a P1 finding for `7.3.tsr.3_7_2_monitoring_storage_type` whose evidence mentions RWX/file storage
- WHEN Chapter 4 and §6.1 are rendered
- THEN the summary mentions block storage or RWX/file storage
- AND the summary does not contain `emptyDir`
- AND the summary does not contain the generic Prometheus/Alertmanager KB description sentence

#### Scenario: FAIL reason used when no pattern matches
- GIVEN a synthetic check with no `summary_patterns` and evidence `widget check: [FAIL] - reason: widgets are on fire`
- WHEN Chapter 4 and §6.1 are rendered
- THEN the summary contains `Widgets are on fire`
- AND it does not dump preceding INFO noise

#### Scenario: Unusable reason is omitted
- GIVEN evidence `[FAIL] - reason: n/a`
- WHEN Chapter 4 and §6.1 are rendered
- THEN the finding id and title still appear
- AND `n/a` is not used as the summary body

#### Scenario: Truncation prefers a sentence end
- GIVEN a FAIL reason whose first sentence is under 220 characters and a long second sentence
- WHEN Chapter 4 and §6.1 are rendered
- THEN the first sentence is kept
- AND the distinctive tail of the second sentence is dropped

#### Scenario: Chapter 4 is a bullet list and §6.1 is a table
- GIVEN one or more P0/P1 findings
- WHEN the report is rendered
- THEN `{CRITICAL_FINDINGS_SUMMARY}` contains markdown bullets of the form `- **{id} — {title}**`
- AND `{CRITICAL_FINDINGS}` contains a table with columns Priority, Finding, Summary
- AND P2/P3 findings are not in that table

### Requirement: §6.2 Observation assembly
§6.2 Observation SHALL be the status-count sentence when square-bracket status tags exist, then the KB `summary_patterns` sentence if matched, then the cleaned first FAIL or WARNING reason. Each prose block SHALL cap at 220 characters. Identical pattern and reason SHALL not be printed twice. Unusable extracted text SHALL be omitted. `[LIMITATION]` and `[SUPPORT LIMITATION]` SHALL NOT be treated as extractable status tags.

#### Scenario: Count, pattern, and remainder all print
- GIVEN tagged evidence that matches a `summary_patterns` row and a distinct FAIL remainder
- WHEN Observation is rendered
- THEN it contains `sub-checks evaluated`
- AND it contains the pattern sentence
- AND it contains the FAIL remainder (when it is not casefold-equal to the pattern)

#### Scenario: Identical pattern and reason print once
- GIVEN a FAIL remainder that casefold-equals the matched pattern text
- WHEN Observation is rendered
- THEN that sentence appears once

#### Scenario: Untagged evidence uses pattern and 220 cap
- GIVEN untagged evidence that matches a webhook `summary_patterns` `contains` value and is longer than 220 characters
- WHEN Observation is rendered
- THEN the pattern or first sentence appears
- AND a distinctive tail past the cap does not appear
- AND no `sub-checks evaluated` sentence is emitted

#### Scenario: FAIL reason without a pattern
- GIVEN tagged evidence with no matching pattern
- WHEN Observation is rendered
- THEN Observation contains the cleaned FAIL remainder
- AND it contains the count sentence

#### Scenario: LIMITATION tags are invisible
- GIVEN evidence whose only non-PASS tags are `[LIMITATION]` or `[SUPPORT LIMITATION]`
- WHEN Observation is rendered
- THEN those tags are not counted as FAIL or WARNING
- AND their remainder is not extracted as the Observation reason
- AND they are lumped into INFO/N/A if counted at all

### Requirement: §6.2 Description and Recommendation
§6.2 Description SHALL be KB `description` only. Empty Description SHALL omit the Description section. Recommendation SHALL be `get_recommendation` output (including the documentation Reference line when a link exists).

#### Scenario: Description is not the TSR remainder
- GIVEN a finding whose evidence is a long TSR FAIL dump
- WHEN §6.2 is rendered
- THEN **Description** is the KB description string
- AND Observation, not Description, carries the evidence-derived prose

### Requirement: Level of Impact
Empty `impact` SHALL render `[NEEDS REVIEW]`. `impact = "none"` SHALL render a visible **None**.

#### Scenario: Missing impact is Needs Review
- GIVEN a finding with empty `impact`
- WHEN `_format_impact_block` runs
- THEN the block is `**Level of Impact:** [NEEDS REVIEW]`

#### Scenario: none is visible
- GIVEN a finding with `impact = "none"`
- WHEN `_format_impact_block` runs
- THEN the label is `None`
- AND the section is not omitted

### Requirement: Finding titles prefer KB title
§6.2 headings and chapter 7 Check column SHALL use KB `title` when set, else `CheckResult.description`.

#### Scenario: Node Disk uses KB title
- GIVEN `7.4.tsr.4_8_1_3_4_node_disk` with KB title `4.8.1.3.4 Default virtualization StorageClass`
- WHEN the finding and chapter 7 Check cell are rendered
- THEN both use that title
- AND they do not keep a TSR HTML "Node Disk" heading in preference to the KB title

### Requirement: TSR Result length
TSR Result HTML SHALL NOT be sliced at 2000 characters. An absurd-input guard of 1_000_000 bytes MAY apply.

#### Scenario: Text past 2000 characters is kept
- GIVEN TSR HTML whose Result cell exceeds 2000 characters
- WHEN it is parsed
- THEN characters after offset 2000 remain in evidence

### Requirement: Parity keeps FAIL/WARNING beside native titles
When a TSR catalog row is FAIL or WARNING, parity SHALL keep that row even if a native check already uses the same normalized title.

#### Scenario: TSR WARNING is not dropped
- GIVEN a native check whose normalized title matches a TSR WARNING catalog row
- WHEN extended/advisory expansion runs
- THEN the TSR WARNING row is still present
- AND the native CSI heading remains `StorageClass provisioners (engine)` when that native check is `7.3.storage.csi`

### Requirement: No PascalCase logging stubs
Layered evaluation SHALL NOT emit PascalCase placeholder ids that collide with TSR catalog snake_case ids.

#### Scenario: Absent logging has no PascalCase stubs
- GIVEN a cluster with no ClusterLogging instance
- WHEN layered evaluation runs
- THEN it does not emit `7.4.tsr.4_1_2_Logging_Storage_Type` (PascalCase) style stub ids
- AND a single 4.1.1 N/A from the logging aggregate MAY remain

### Requirement: Registry Unmanaged or Removed is INFO plus finding
`7.5.registry_health` SHALL treat Managed as PASS, Unmanaged or Removed as INFO, and other values as WARNING. INFO SHALL become a P3 finding via `finding_on_info`.

#### Scenario: Unmanaged is INFO and P3
- GIVEN image registry `managementState` Unmanaged
- WHEN the health evaluator and `derive_findings` run
- THEN check status is INFO
- AND a P3 finding exists
- AND `spec.storage.managementState` is not the signal

### Requirement: Live-migratable engine check
The engine SHALL collect VM and VMI objects and emit `7.4.cnv.live_migratable` with KubeVirt `LiveMigratable=False` reason/message. It SHALL NOT steal TSR worksheet title `4.8.2.1.1.3`.

#### Scenario: Non-migratable VMI includes reason
- GIVEN a VMI with `LiveMigratable=False` and a condition message
- WHEN the engine check runs
- THEN evidence includes that reason or message

### Requirement: Pod-restart collection gap
After parity expansion, if TSR 5.5 names `namespace/name` pods absent from collected `pods_all`, the engine SHALL append a collection-gap sentence. It SHALL NOT copy the TSR pod list into the restart filter. The restart rule remains `restartCount > 10`, first 3 of N.

#### Scenario: TSR names a pod missing from collection
- GIVEN TSR Result naming a pod key that is not in `pods_all`
- WHEN the annotate hook runs
- THEN engine evidence includes a collection-gap sentence
- AND production prose counts the gap rather than listing customer pod names

### Requirement: Missing TSR or CCX leaves catalog SKIPPED
Extended/advisory catalog rows SHALL be SKIPPED when TSR HTML or live Insights data is missing. CCX `status_hint` SHALL NOT apply unless `--ccx-baseline-status`.

#### Scenario: Extended without TSR runtime is skipped
- GIVEN `--check-profile extended` and no TSR HTML runtime
- WHEN expansion runs
- THEN catalog rows are SKIPPED rather than invented PASS/FAIL

### Requirement: Documentation links are out of band
This capability SHALL NOT require rewriting existing KB `[checks.links]` URLs. Link review is a separate CLI (`make hc-link-apply`).

#### Scenario: Report engine does not verify URLs
- GIVEN a KB `links` table
- WHEN `make hc-report` runs
- THEN it may append a Reference line from `get_doc_link`
- AND it does not fetch or rewrite those URLs
