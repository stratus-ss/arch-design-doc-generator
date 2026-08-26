# Health Check Report Engine

> **Canonical spec:** this file (`openspec/specs/hc-report-engine/spec.md`). Do not recreate `agent_planning/openspec/specs/`.
>
> **Baseline date:** 2026-08-21 (landed Chunks A–G). Chunk H deltas live in `openspec/changes/hc-feedback-chunk-h/` until archived. `hc-omit-findings` is archived here (2026-08-25). Scoring veracity (`scoring_basis`, native FAIL/WARNING honesty vs OCP 4.22) is archived here (2026-08-25). `hc-html-pdf-report-file` is archived here (2026-08-26). `hc-narrative-paragraph-spacing` is archived here (2026-08-26).

## Purpose

`make hc-report` turns collected OpenShift cluster JSON (and optional TSR HTML / CCX runtime) into a consultant-facing markdown report. The engine evaluates checks, derives P0–P3 findings from a TOML knowledge base, and fills `{SLOT}` placeholders in `templates/Health_Check/Template_HC_Report.md`. AI is excluded from check evaluation. An optional post-render Cursor step may rewrite Chapter 3 and Chapter 8 when `HC_SUMMARY_CONCLUSION=1`.

## Requirements

### Requirement: No AI on the Health Check path
The Health Check **engine** CLI (`scripts/health_check/hc_report/cli.py`) SHALL NOT import or invoke the HLD/LLD AI stack. An optional **post-render** process MAY draft Chapter 3 and Chapter 8 after `generate_report.py` has written markdown.

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
- THEN it accepts `--results-dir`, `--output-dir`, `--config`, `--template`, `--exec-summary`, `--check-profile` (`core` | `extended` | `advisory`), `--ccx-baseline-status`, `--catalog-path`, `--tsr-html`, `--dry-run`, `--omit-check-ids`, and `--omit-strict`
- AND those existing flag names are not renamed

### Requirement: Optional Chapter 6 omit by check ID
When `--omit-check-ids` is omitted or the loaded list is empty, generate SHALL write only the unpruned Health Check markdown and full audit JSON and SHALL remove that cluster's `{stem}_pruned.md` if it exists. When the omit list is non-empty, generate SHALL also write `{stem}_pruned.md` whose Chapter 6 omits matched findings. Chapter 7 SHALL still list every check. Audit JSON SHALL keep the unfiltered findings with original IDs.

#### Scenario: No omit flag leaves a single report
- GIVEN no `--omit-check-ids`
- WHEN generate runs
- THEN only the unpruned Health Check markdown and full audit JSON are written
- AND any previous `{stem}_pruned.md` for that cluster is removed if it existed

#### Scenario: Non-empty omit writes pruned Chapter 6
- GIVEN a non-empty omit file
- WHEN generate runs
- THEN original markdown and audit JSON still contain all findings
- AND `{stem}_pruned.md` Chapter 6 omits matched findings
- AND Chapter 7 tables still include those checks

#### Scenario: Grouped finding drops on any member
- GIVEN a grouped finding
- WHEN any member check ID is listed
- THEN the whole finding is absent from pruned Chapter 6

#### Scenario: Strict unmatched does not write pruned
- GIVEN `--omit-strict` and an ID not on any finding
- WHEN generate runs
- THEN exit code is 1
- AND `{stem}_pruned.md` is not written

#### Scenario: Discover prefers pruned peer
- GIVEN `discover_report_markdown` and both `Foo.md` and `Foo_pruned.md`
- WHEN discover runs
- THEN only `Foo_pruned.md` is returned (same directory)

### Requirement: Chapter 3 and 8 paragraph spacing in HTML/PDF
Chapters 3 (Executive Summary) and 8 (Conclusions) SHALL render with visible whitespace between consecutive paragraphs in both `make hc-html` and `make hc-pdf` exports. Other chapters SHALL keep the global tight paragraph margins unchanged.

#### Scenario: PDF wraps narrative chapters in a spacing div
- GIVEN pandoc HTML containing `<h2>Chapter 3. Executive Summary</h2>` and `<h2>Chapter 8. Conclusions</h2>`
- WHEN `pdf_preprocess.process` runs
- THEN those two chapter ranges are wrapped in `<div class="hc-narrative-chapter">`
- AND the injected CSS contains `.hc-narrative-chapter p { margin-bottom: 1em; }`
- AND Chapter 6 is not wrapped

#### Scenario: HTML collapsible adds narrative class on matching chapters
- GIVEN pandoc HTML with Chapter 3 and Chapter 8 headings
- WHEN `html_collapsible.collapsify` runs
- THEN the `<details>` element for Chapter 3 has `class="hc-narrative-chapter"`
- AND the `<details>` element for Chapter 8 has `class="hc-narrative-chapter"`
- AND Chapter 6 `<details>` does not have that class
- AND the injected collapsible CSS contains the `.hc-narrative-chapter p` rule

#### Scenario: Other chapters keep tight margins
- GIVEN any chapter not matching "Chapter 3.*Executive Summary" or "Chapter 8.*Conclusions"
- WHEN either export pipeline runs
- THEN the chapter's paragraphs use the global `p` margin (5–6px)

### Requirement: Named REPORT file for HTML/PDF export
When `hc_export_paths.py` is invoked without `--source`, discover-all SHALL keep preferring `{stem}_pruned.md` over the unpruned sibling. When `--source` is set, the process SHALL export that file only and SHALL NOT apply pruned-peer preference. Sidecar markdown and missing paths SHALL exit 1 without discovering other reports. Out-of-tree sources SHALL map to `export_root / {stem}.{extension}`. In-tree regenerate (canonical dest already present) SHALL exit 0 without `--allow-overwrite`. Out-of-tree dest that already exists SHALL exit 4 unless `--allow-overwrite`.

#### Scenario: Discover-all still prefers pruned peer
- GIVEN no `--source` and both `Foo.md` and `Foo_pruned.md` in the report directory
- WHEN discover-all mapping runs
- THEN only `Foo_pruned.md` is exported

#### Scenario: Named unpruned file ignores pruned sibling
- GIVEN `--source Foo.md` with in-tree `Foo_pruned.md`
- WHEN named export runs
- THEN the mapping source is `Foo.md`
- AND stderr contains `WARNING: PRUNED SIBLING IGNORED`

#### Scenario: Out-of-tree source maps by basename
- GIVEN `--source` outside the report directory
- WHEN named export runs
- THEN destination is `export_root` plus the markdown stem and extension
- AND stderr contains `WARNING: SOURCE OUTSIDE REPORT TREE`

#### Scenario: In-tree regenerate does not require overwrite consent
- GIVEN an in-tree source whose canonical dest already exists
- WHEN named export runs without `--allow-overwrite`
- THEN exit code is 0

#### Scenario: Out-of-tree existing dest requires consent
- GIVEN an out-of-tree source and an existing basename dest
- WHEN named export runs without `--allow-overwrite`
- THEN exit code is 4
- AND the dest file bytes are unchanged

#### Scenario: Allow overwrite succeeds
- GIVEN an out-of-tree source and an existing basename dest
- WHEN named export runs with `--allow-overwrite`
- THEN exit code is 0

#### Scenario: Missing or sidecar named source does not discover-all
- GIVEN `--source` missing or a sidecar filename and other valid report markdown in the directory
- WHEN named export runs
- THEN exit code is 1
- AND stdout has no mapping for those other reports

### Requirement: Template slot names
`render_report` SHALL substitute the named `{SLOT}` tokens from `templates/Health_Check/Template_HC_Report.md` and SHALL NOT rename them.

#### Scenario: Critical-finding slots exist
- GIVEN the Health Check report template
- WHEN it is filled
- THEN Chapter 4 is Purpose and Engagement Approach and the result-legend table
- AND `{CLIENT}`, `{CLUSTER_ID}`, and `{CAPTURE_MONTH_YEAR}` appear in Chapter 4
- AND `{CRITICAL_FINDINGS}` is §6.1
- AND `{FINDINGS_SECTIONS}` is §6.2

### Requirement: CheckResult and Finding fields
Cross-module objects SHALL keep the `CheckResult` and `Finding` field names used by evaluators, findings, renderer, and audit JSON.

#### Scenario: CheckResult status vocabulary
- GIVEN a `CheckResult`
- WHEN it is stored
- THEN `status` is one of `PASS`, `FAIL`, `WARNING`, `INFO`, `NOT_APPLICABLE`, `SKIPPED`
- AND `source` is `deterministic`, `tsr`, or `ccx`

#### Scenario: CheckResult scoring_basis vocabulary
- GIVEN a `CheckResult`
- WHEN it is stored
- THEN `scoring_basis` is `doc_backed`, `engine_policy`, or empty

#### Scenario: Audit JSON includes scoring_basis
- GIVEN generate writes audit JSON
- WHEN a check is serialized
- THEN `checks[].scoring_basis` is present

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

#### Scenario: Recommendation joins optional verification
- GIVEN a KB row with a recommendation paragraph and a `verification` field
- WHEN `get_recommendation` runs
- THEN the returned string is the paragraph, a blank line, a bold `**Verification:**` line (not a markdown heading), then the verification body
- AND HTML/PDF still render a single **Recommendation:** label
- AND an empty `verification` omits the Verification line entirely
- AND an empty recommendation still returns `[NEEDS REVIEW]` even if `verification` is populated

#### Scenario: Version-gated recommendation
- GIVEN `recommendation_supported_versions` that does not include the requested OCP minor
- WHEN `get_recommendation` runs
- THEN the returned text starts with `[NEEDS REVIEW]`
- AND it still includes the candidate guidance

### Requirement: KB content_from alias
An alias KB row MAY set `content_from` to an exact canonical `check_id`. `load_kb()` SHALL copy inherited content from that target in a single hop and SHALL keep the alias `check_id` and finding flags on the alias. Overlay, chains, self-references, missing targets, pattern-row pointers, and glob targets SHALL raise `ValueError`.

#### Scenario: Alias inherits content and keeps local title and flags
- GIVEN alias `content_from = "canonical.id"` and omitted inherited keys
- WHEN `load_kb()` runs
- THEN `get_entry(alias)` recommendation, verification, description, impact, and links equal the canonical row
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
- GIVEN alias sets a non-empty `recommendation` or `verification` (or any other inherited field)
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
FAIL without a P0 keyword SHALL be P1 unless a valid KB `priority_hint` overrides. WARNING with a P2 keyword SHALL be P2, otherwise P3, unless a valid hint overrides. CCX FAIL SHALL be P2 and CCX WARNING SHALL be P3 unless a valid hint overrides. A KB `priority_hint` of `P0`/`P1`/`P2`/`P3` SHALL replace the encoded priority. Empty or invalid hints SHALL leave the encoded priority unchanged.

#### Scenario: Ordinary FAIL is P1
- GIVEN a deterministic FAIL whose description does not match P0 keywords
- AND the check has an empty `priority_hint`
- WHEN `derive_findings` runs
- THEN priority is P1

#### Scenario: Quota and MTV FAIL is P3
- GIVEN a deterministic FAIL on any of `7.6.rq`, `7.6.tsr.6_1_1_quota_and_resources`, `7.6.tsr.6_1_1_1_quota_resources_project_assignment`, `7.6.tsr.6_1_1_2_cluster_quota_configuration`, `7.4.tsr.4_8_5_1_1_quota_and_resources`, `7.4.tsr.4_12_1_1_1_mtv_installation_and_state`, `7.4.tsr.4_12_1_1_2_operator_subscription_posture`, `7.4.tsr.4_12_1_2_mtv_supported_configuration`
- WHEN `derive_findings` runs
- THEN priority is P3

#### Scenario: Hinted WARNING with P2 keyword is P3
- GIVEN a WARNING on `7.6.rq` whose description matches a P2 keyword
- WHEN `derive_findings` runs
- THEN priority is P3

### Requirement: Finding grouping
Checks that share a non-empty KB `finding_group` SHALL collapse to one §6.2 finding. Chapter 7 SHALL still list every check.

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

### Requirement: §6.1 summary text
§6.1 Summary (and the `{CRITICAL_FINDINGS_SUMMARY}` helper) SHALL use KB `summary_patterns` (first `contains` substring match on finding evidence) then the cleaned first FAIL or WARNING reason. They SHALL NOT use KB `description`. Unusable text (`n/a`, `none`, `unknown`, `na`, too short, no letters) SHALL be omitted. Prose SHALL cap at 220 characters, preferring a sentence end then a word boundary.

#### Scenario: Pattern wins over emptyDir KB description
- GIVEN a P1 finding for `7.3.tsr.3_7_2_monitoring_storage_type` whose evidence mentions RWX/file storage
- WHEN §6.1 and the critical-findings summary helper are rendered
- THEN the summary mentions block storage or RWX/file storage
- AND the summary does not contain `emptyDir`
- AND the summary does not contain the generic Prometheus/Alertmanager KB description sentence

#### Scenario: FAIL reason used when no pattern matches
- GIVEN a synthetic check with no `summary_patterns` and evidence `widget check: [FAIL] - reason: widgets are on fire`
- WHEN §6.1 and the critical-findings summary helper are rendered
- THEN the summary contains `Widgets are on fire`
- AND it does not dump preceding INFO noise

#### Scenario: Unusable reason is omitted
- GIVEN evidence `[FAIL] - reason: n/a`
- WHEN §6.1 and the critical-findings summary helper are rendered
- THEN the finding id and title still appear
- AND `n/a` is not used as the summary body

#### Scenario: Truncation prefers a sentence end
- GIVEN a FAIL reason whose first sentence is under 220 characters and a long second sentence
- WHEN §6.1 and the critical-findings summary helper are rendered
- THEN the first sentence is kept
- AND the distinctive tail of the second sentence is dropped

#### Scenario: Critical summary helper is a bullet list and §6.1 is a table
- GIVEN one or more P0/P1 findings
- WHEN the report is rendered
- THEN `{CRITICAL_FINDINGS_SUMMARY}` contains markdown bullets of the form `- **{id} — {title}**`
- AND `{CRITICAL_FINDINGS}` contains a table with columns Priority, Finding, Summary
- AND P2/P3 findings are not in that table
- AND Chapter 4 does not contain `{CRITICAL_FINDINGS_SUMMARY}`

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

#### Scenario: Recommendation single newlines become HTML breaks
- GIVEN a finding whose recommendation contains `**Verification:**` and numbered steps separated by single newlines
- WHEN §6.2 is rendered to markdown
- THEN those newlines are emitted as HTML <br> so pandoc does not collapse the steps into one paragraph
- AND pandoc renders the label as `<strong>Verification:</strong>`
- AND the report still has exactly one `**Recommendation:**` label
- AND there is no `##### Verification` heading
- AND a one-line recommendation does not gain <br>

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

### Requirement: Finding titles prefer KB title
§6.2 headings and chapter 7 Check column SHALL use KB `title` when set, else `CheckResult.description`.

#### Scenario: Node Disk uses KB title
- GIVEN `7.4.tsr.4_8_1_3_4_node_disk` with KB title `4.8.1.3.4 Default virtualization StorageClass`
- WHEN the finding and chapter 7 Check cell are rendered
- THEN both use that title
- AND they do not keep a TSR HTML "Node Disk" heading in preference to the KB title

### Requirement: TSR Result length
TSR Result HTML SHALL NOT be sliced at 2000 characters. Parsed evidence SHALL be clipped at 32_000 characters with a truncation marker.

#### Scenario: Text past 2000 characters is kept
- GIVEN TSR HTML whose Result cell exceeds 2000 characters and is under 32_000
- WHEN it is parsed
- THEN characters after offset 2000 remain in evidence

#### Scenario: Oversized Result is clipped
- GIVEN TSR HTML whose Result cell exceeds 32_000 characters
- WHEN it is parsed
- THEN evidence length is at most 32_000
- AND the evidence ends with the truncation marker

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

### Requirement: Optional post-render Chapter 3/8 draft
When `HC_SUMMARY_CONCLUSION=1`, the container SHALL run `draft_summary_conclusion.py --in-place` on each generated Health Check markdown report **after** `generate_report.py` succeeds. When `HC_SUMMARY_CONCLUSION` is unset, empty, or `0`, no model SHALL be invoked during `make hc-report`.

#### Scenario: Opt-in draft runs after generate
- GIVEN `HC_SUMMARY_CONCLUSION=1` and a written Health Check markdown report
- WHEN `cmd_hc_report` finishes `generate_report.py` successfully
- THEN `draft_summary_conclusion.py --in-place` runs as a separate process
- AND `hc_report/cli.py` is not the process that calls `invoke_ai`

#### Scenario: Opt-in draft targets only this generate run
- GIVEN `HC_SUMMARY_CONCLUSION=1` and `output/Health_Check_Report` already contains markdown from prior clusters or dates
- WHEN `generate_report.py` writes one report (and optional `{stem}_pruned.md`) this run
- THEN `draft_summary_conclusion.py --in-place` runs only on that newly written report
- AND it prefers `{stem}_pruned.md` when this run also wrote it
- AND it does not rewrite other markdown already in the output directory

#### Scenario: Default report is deterministic
- GIVEN `HC_SUMMARY_CONCLUSION` unset
- WHEN `make hc-report` runs
- THEN no model is invoked
- AND Chapter 3 remains the engine placeholder unless `--exec-summary` was passed to generate

#### Scenario: Unsupported container tool fails closed
- GIVEN `--in-place` and `AI_TOOL=claude` (or `codex`) while that tool is not in `CONTAINER_DRAFT_TOOLS`
- WHEN `draft_summary_conclusion.py` runs
- THEN it exits 2 without rewriting the report

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

### Requirement: MachineConfigPool engine scoring
`_evaluate_mcp` SHALL treat a paused pool with matching machine counts as a pause warning, not an incomplete rollout.

#### Scenario: Paused pool with matching counts is not incomplete rollout
- GIVEN a `MachineConfigPool` with `spec.paused=true`, `Degraded=False`, `Updating=False`, `Updated=False`, and `updatedMachineCount == readyMachineCount == machineCount > 0`
- WHEN `_evaluate_mcp` / `evaluate_topology` scores that pool
- THEN status is `WARNING`
- AND evidence includes that the pool is paused
- AND evidence does not say `not fully updated`
