# Health Check Report Engine

> **Canonical spec:** this file (`openspec/specs/hc-report-engine/spec.md`). Do not recreate `agent_planning/openspec/specs/`.
>
> **Baseline date:** 2026-08-21 (landed Chunks A–G). Chunk H deltas live in `openspec/changes/hc-feedback-chunk-h/` until archived. `hc-omit-findings` is archived here (2026-08-25). Scoring veracity (`scoring_basis`, native FAIL/WARNING honesty vs OCP 4.22) is archived here (2026-08-25). `hc-tsr-pass-host-condense` is archived here (2026-08-26). `hc-tsr-inventory-condense` is archived here (2026-08-26). `hc-html-pdf-report-file` is archived here (2026-08-26). `hc-narrative-paragraph-spacing` is archived here (2026-08-26). `hc-toc-chapter-links` is archived here (2026-08-26). `hc-live-parity-collect` is archived here (2026-08-28). `hc-live-parity-evaluate` is archived here (2026-08-28). `hc-native-etcd-worksheets` is archived here (2026-08-29). `hc-native-registry-monitoring-storage` is archived here (2026-08-29). `hc-native-node-role-gc` is archived here (2026-08-29). `hc-native-virt-orig-leaves` is archived here (2026-08-29). `hc-native-alias-7-5-7-6` is archived here (2026-08-29). `hc-native-alias-7-3` is archived here (2026-08-29). `hc-native-alias-7-1-7-2` is archived here (2026-08-29). `hc-native-virt-p3` is archived here (2026-08-29). `hc-native-virt-p3-remainder` is archived here (2026-08-29). `hc-native-firewalls` is archived here (2026-08-29). `hc-native-csi-allowlist` is archived here (2026-08-29). `hc-native-quota-coverage` is archived here (2026-08-29). `hc-native-pod-requests` is archived here (2026-08-29). `hc-native-netpol-prune` is archived here (2026-08-29). `hc-native-image-patch` is archived here (2026-08-29). `hc-native-olm-leftovers` is archived here (2026-08-29). `hc-native-upgrade-failed-hops` is archived here (2026-08-29). `hc-chapter7-alias-hide` is archived here (2026-08-29).

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
When `--omit-check-ids` is omitted or the loaded list is empty, generate SHALL write only the unpruned Health Check markdown and full audit JSON and SHALL remove that cluster's `{stem}_pruned.md` if it exists. When the omit list is non-empty, generate SHALL also write `{stem}_pruned.md` whose Chapter 6 omits matched findings. Chapter 7 SHALL still list those omit-listed checks (the `--omit-check-ids` filter does not hide Chapter 7). Checks whose KB entry has a non-empty `content_from` SHALL still be omitted from Chapter 7 tables and category stats. Audit JSON SHALL keep the unfiltered findings with original IDs.

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

### Requirement: Chapter 2 TOC is in-document links
HTML and PDF export SHALL turn Chapter 2 numbered chapter lines into fragment links (`a.hc-toc-link`) whose `href` matches the corresponding report-chapter `h2` `id`. Numbered steps outside Chapter 2 SHALL stay unlinked. HTML SHALL open ancestor `<details>` when a TOC link is activated.

#### Scenario: TOC lines link to chapter heading ids
- GIVEN pandoc HTML with Chapter 1–3 headings that have `id`s, a Chapter 2 body of `1. Introduction<br />2. Table of Contents<br />3. Executive Summary`, and a later `1. Confirm…` paragraph
- WHEN `linkify_chapter_toc` runs (HTML `process` and PDF `process`)
- THEN the Chapter 2 Introduction and Executive Summary lines are `a.hc-toc-link` pointing at those heading ids
- AND the later `1. Confirm` line is not a TOC link

#### Scenario: HTML TOC click opens collapsed chapters
- GIVEN exported HTML from `html_collapsible.process`
- WHEN the user activates `a.hc-toc-link`
- THEN ancestor `<details>` are opened and the heading target is scrolled into view (script: click on `a.hc-xref-link, a.hc-toc-link` plus existing hashchange)

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

### Requirement: CONTENT_FROM rows MAY alias to a native check_id
Plan 1 CONTENT_FROM KB rows MAY be sparse aliases (`content_from` plus title and finding flags). The target SHALL be a native `check_id` when one exists, otherwise a non-alias canonical. Loader fail-closed rules (single hop, no overlay, exact target) SHALL remain unchanged.

#### Scenario: Sparse alias inherits native prose
- GIVEN a CONTENT_FROM alias with `content_from` set to a native `check_id` and omitted inherited keys
- WHEN `load_kb()` runs
- THEN the alias recommendation, verification, description, impact, and links equal the native row
- AND the alias `check_id` and title stay local

### Requirement: New CONTENT_FROM aliases omit Chapter 6 findings
New aliases created for Plan 1 CONTENT_FROM rows SHALL set `include_in_findings = false`. Chapter 7 tables and category stats SHALL omit the alias check. The native target remains eligible for Chapter 6.

#### Scenario: New alias is not a Chapter 6 finding
- GIVEN a new CONTENT_FROM alias with `include_in_findings = false`
- WHEN `derive_findings` runs on a FAIL or WARNING for that alias `check_id`
- THEN that alias `check_id` does not appear as a finding or finding-group member
- AND Chapter 7 tables and category stats omit that alias check

### Requirement: Virt CONTENT_FROM SHALL NOT dump onto identification-and-state
OpenShift Virtualization TSR 4.8 leaves SHALL alias to native `7.4.cnv.state`, `7.4.cnv.kubevirt`, `7.4.cnv.pods`, or `7.4.cnv.live_migratable` by story. Distinct virt TSR prose rows SHALL remain canonical. The set of virt aliases SHALL NOT all target `7.4.tsr.4_8_1_1_1_identification_and_state`.

#### Scenario: Virt family uses native CNV targets
- GIVEN virt CONTENT_FROM aliases after this change
- WHEN `load_kb()` resolves those aliases
- THEN at least one alias has `content_from` equal to a `7.4.cnv.*` native id
- AND not every virt alias has `content_from = "7.4.tsr.4_8_1_1_1_identification_and_state"`

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
- AND Chapter 7 still lists those checks when `content_from` is empty

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
- GIVEN a deterministic FAIL on any of `7.6.rq`, `7.6.quota.coverage`, `7.4.cnv.vm_quota`, `7.4.tsr.4_12_1_1_1_mtv_installation_and_state`, `7.4.tsr.4_12_1_1_2_operator_subscription_posture`, `7.4.tsr.4_12_1_2_mtv_supported_configuration`
- WHEN `derive_findings` runs
- THEN priority is P3

#### Scenario: Hinted WARNING with P2 keyword is P3
- GIVEN a WARNING on `7.6.rq` whose description matches a P2 keyword
- WHEN `derive_findings` runs
- THEN priority is P3

### Requirement: Finding grouping
Checks that share a non-empty KB `finding_group` SHALL collapse to one §6.2 finding. Chapter 7 SHALL still list each grouped check that has empty `content_from`.

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
TSR Result HTML SHALL NOT be sliced at 2000 characters. Parsed evidence SHALL be condensed (PASS host groups and inventory dumps) and then clipped at 32_000 characters with a truncation marker.

#### Scenario: Text past 2000 characters is kept
- GIVEN TSR HTML whose Result cell exceeds 2000 characters and is under 32_000
- WHEN it is parsed
- THEN characters after offset 2000 remain in evidence

#### Scenario: Oversized Result is clipped
- GIVEN TSR HTML whose Result cell exceeds 32_000 characters
- WHEN it is parsed
- THEN evidence length is at most 32_000
- AND the evidence ends with the truncation marker

### Requirement: TSR identical pass-host condensation
TSR leaf Result text SHALL collapse fully-ok per-host blocks inside a role node group (`MASTER NODES:::`, `RHCOS NODES:::`, and the same `* NODES` header shape) before clipping. A host entry MAY be `hostname:` plus following status lines, or `hostname:   [PASS]   - reason: …` on one line. A body is fully ok when it has `[PASS]` or `[INFO]` and none of `[FAIL]`, `[WARNING]`, `[WARN]`, `[LIMITATION]`, `[SUPPORT LIMITATION]`, `[SKIP]`, `[SKIPPED]`, `[NOT_APPLICABLE]`, `[NA]`. `{group label}::>ALL NODES:` SHALL be emitted only when every host in that group is fully ok (two or more hosts). A mixed group with two or more fully-ok hosts and at least one non-ok host SHALL emit `{group label}::>PASS NODES:` plus one ok body, SHALL keep every non-ok hostname, and SHALL NOT emit ALL NODES. When every host is fully ok, differing PASS/INFO reason text MAY still collapse to one representative body. Groups that already contain `>ALL NODES:` SHALL be left unchanged. Bare `NODES::` SHALL NOT be a collapse group. After at least one host in a group, a non-empty line with no result-status token (`mtu`, `ipv4.enabled`) SHALL end that group so later `MASTER NODES:::` / `RHCOS NODES:::` blocks still collapse. CCX Message cells SHALL NOT be condensed. Check `status` SHALL NOT change because of condensation.

#### Scenario: Identical worker PASS hosts collapse
- GIVEN a TSR Result with `RHCOS NODES:::` and two or more hosts whose bodies are identical PASS-only lines
- WHEN the leaf Result is parsed
- THEN evidence contains `RHCOS NODES::>ALL NODES:`
- AND it contains one copy of that PASS body
- AND it does not list each of those worker hostnames

#### Scenario: Mixed group emits PASS NODES not ALL NODES
- GIVEN a role node group with three hosts where one has `[WARNING]` or `[SUPPORT LIMITATION]` and the other two have PASS-only bodies
- WHEN the leaf Result is parsed
- THEN evidence contains `PASS NODES`
- AND the non-ok hostname remains
- AND the PASS hostnames are absent
- AND that group has no ALL NODES line

#### Scenario: Independent groups collapse independently
- GIVEN `MASTER NODES:::` with a `[SUPPORT LIMITATION]` host and `RHCOS NODES:::` with identical PASS-only hosts
- WHEN the leaf Result is parsed
- THEN the MASTER LIMITATION hostname remains
- AND RHCOS PASS hosts collapse to `RHCOS NODES::>ALL NODES:`

#### Scenario: All-ok group collapses even when PASS reasons differ
- GIVEN two hosts in the same role group with different PASS reason text
- WHEN the leaf Result is parsed
- THEN evidence contains `RHCOS NODES::>ALL NODES:`
- AND those hostnames are absent

#### Scenario: Heterogeneous ok bodies collapse when every host is ok
- GIVEN a role node group with four hosts: two share PASS body A, two share PASS body B (different from A)
- WHEN the leaf Result is parsed
- THEN evidence contains `RHCOS NODES::>ALL NODES:`
- AND those hostnames are absent

#### Scenario: Native ALL NODES is not rewritten
- GIVEN Result text that already contains `RHCOS NODES::>ALL NODES:`
- WHEN the leaf Result is parsed
- THEN that ALL NODES line remains
- AND no extra host lines are invented for that group

#### Scenario: Inline hostname PASS lines collapse
- GIVEN `RHCOS NODES:::` hosts whose status is on the same line as the hostname (`hostname:   [PASS]   - reason: …`)
- WHEN the leaf Result is parsed
- THEN evidence contains `RHCOS NODES::>ALL NODES:`
- AND those hostnames are absent

#### Scenario: Repeated field groups keep labels and collapse each block
- GIVEN `state` then `MASTER NODES:::` / `RHCOS NODES:::` PASS hosts, then `mtu`, then another `MASTER NODES:::` / `RHCOS NODES:::` PASS block
- WHEN the leaf Result is parsed
- THEN `state` and `mtu` remain
- AND each role group collapses independently
- AND worker hostnames are absent

### Requirement: TSR inventory dump condensation
After host condensation and before the 32_000-character clip, TSR leaf Result text SHALL condense inventory dumps. A ` · ` header is a line whose fields all match `^[A-Z][A-Z0-9 /._-]*$`. Data rows contain ` · `, are not headers, and have no result-status token. Signature is fields after the first two. Groups of two or more identical signatures SHALL keep the header (when present), the first row, and `({n} more)`. A run of two or more data rows with no ALL-CAPS header SHALL still group by signature. A non-data line SHALL end the current run; later data rows SHALL form a new run and MAY collapse without a new header. A line containing `(nconnect=` SHALL group by that token; two or more SHALL keep the first line and `({n} more NFS mounts with {token})`. A `node <hostname>:` or `node <hostname> <qualifier>:` line with a result-status token, or the exact trailer `nfs-slot-tuning.service: not active or missing`, SHALL group by qualifier plus status body; two or more SHALL emit `({n} nodes):   {body}` for unqualified lines and `({n} nodes) <qualifier>:   {body}` for qualified lines, and SHALL NOT emit ALL NODES. A line matching `<ns>:<name>   [WARNING]   - looks unhealthy` SHALL group by namespace plus name with trailing `-[a-z0-9]+-[a-z0-9]{5}` stripped; two or more SHALL keep the first line and `({n} more pods)`. Unique rows stay. Check `status` SHALL NOT change.

#### Scenario: Identical table remainders collapse
- GIVEN a `NAMESPACE · VMI · LIVEMIGRATABLE` header and three data rows that share remainder `true`
- WHEN the leaf Result is parsed
- THEN evidence contains the header and one data row
- AND evidence contains `(2 more)`
- AND it does not list all three identity names

#### Scenario: Distinct table remainders stay separate
- GIVEN a `NAMESPACE · NAME · TYPE` header, two rows with remainder `bridge`, and one row with remainder `bond`
- WHEN the leaf Result is parsed
- THEN evidence contains one `bridge` example and `(1 more)`
- AND the `bond` row remains in full

#### Scenario: Headerless table remainders collapse
- GIVEN three ` · ` data rows with no ALL-CAPS header that share remainder `ReadWriteMany · Bound · yes`
- WHEN the leaf Result is parsed
- THEN evidence contains one data row
- AND evidence contains `(2 more)`

#### Scenario: Table resumes after a broken row
- GIVEN a `NAMESPACE · PVC · PHASE · STORAGECLASS` header, two matching data rows, a line with no ` · `, then two more matching data rows
- WHEN the leaf Result is parsed
- THEN evidence contains two `(1 more)` markers
- AND the broken line remains

#### Scenario: Nconnect mounts collapse by token
- GIVEN two NFS mount lines that share `(nconnect=default/1)`
- WHEN the leaf Result is parsed
- THEN evidence contains one mount line
- AND evidence contains `(1 more NFS mounts with (nconnect=default/1))`

#### Scenario: Repeated node warnings collapse without ALL NODES
- GIVEN two `node examplehost061.cl1.cluster.example.com:` WARNING lines with the same reason body
- WHEN the leaf Result is parsed
- THEN evidence contains `(2 nodes):`
- AND evidence does not contain ALL NODES for those lines

#### Scenario: Qualified node status lines collapse
- GIVEN three `node <hostname> cmdline:` INFO lines with the same reason body
- WHEN the leaf Result is parsed
- THEN evidence contains `(3 nodes) cmdline:`
- AND those hostnames are absent

#### Scenario: Unhealthy pods collapse by workload
- GIVEN two WARNING pod lines in the same namespace whose names share a prefix after stripping `-[a-z0-9]+-[a-z0-9]{5}`
- WHEN the leaf Result is parsed
- THEN evidence contains one pod line
- AND evidence contains `(1 more pods)`

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

### Requirement: FeatureGate native scoring from collected CR
When FeatureGate is collected, native `7.3.net.featuregates` SHALL score `spec.featureSet`. Empty or `Default` SHALL be PASS. `TechPreviewNoUpgrade` or `CustomNoUpgrade` SHALL be FAIL with `scoring_basis=doc_backed`. Missing capture SHALL remain SKIPPED. Clusteroperators SHALL not be used as a TechPreview detector. There SHALL NOT be a second FeatureGate check_id.

#### Scenario: FeatureGate not collected
- GIVEN FeatureGate is not in the collection
- WHEN the check runs
- THEN status is SKIPPED

#### Scenario: FeatureGate Default or empty
- GIVEN FeatureGate `spec.featureSet` is empty or `Default`
- WHEN the check runs
- THEN status is PASS

#### Scenario: FeatureGate TechPreviewNoUpgrade
- GIVEN FeatureGate `spec.featureSet` is `TechPreviewNoUpgrade`
- WHEN the check runs
- THEN status is FAIL
- AND `scoring_basis` is `doc_backed`

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

### Requirement: Optional product and platform CR JSON on collect
Live `hc-collect` SHALL write the following check_name files (plus `.meta.json`) via `hc_capture_json`. Missing CRD or empty items SHALL be `_hc_not_found`, not a failed collect.

#### Scenario: New capture names exist after collect
- GIVEN a successful `hc-collect` run
- WHEN the results directory is listed
- THEN these files exist under their category dirs:
  `03_base_platform/insightsoperator.json`,
  `05_components/dns_pods.json`, `featuregate.json`, `metallb.json`, `ipsecconfig.json`,
  `sriovnetwork.json`, `performanceprofile.json`, `localvolume.json`, `csidriver.json`,
  `06_layered/odf_storagecluster.json`, `rhoso_controlplane.json`, `mtv_controller.json`,
  `07_cluster_health/pdb.json`,
  `09_security/fileintegrity.json`
- AND collect does not add a second DNS cluster capture besides existing `dns_config.json`

### Requirement: Optional product CRs score NOT_APPLICABLE when absent
Native evaluation of optional product CRs SHALL treat `_hc_not_found` or empty `items` as NOT_APPLICABLE, not FAIL. Collection `_hc_error` SHALL be SKIPPED, not NOT_APPLICABLE. This applies to ODF StorageCluster (`7.4.odf.state`), RHOSO OpenStackControlPlane (`7.4.rhoso.state`), LocalVolume (`7.3.storage.localvolume`), FileIntegrity (`7.7.file_integrity`), and MetalLB when the operator is not installed.

#### Scenario: ODF StorageCluster not found
- GIVEN `06_layered/odf_storagecluster.json` is `_hc_not_found` or has empty items
- WHEN core evaluation runs
- THEN `7.4.odf.state` status is NOT_APPLICABLE

#### Scenario: RHOSO control plane not found
- GIVEN `06_layered/rhoso_controlplane.json` is `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.4.rhoso.state` status is NOT_APPLICABLE

#### Scenario: LocalVolume not found
- GIVEN `05_components/localvolume.json` is `_hc_not_found` or has empty items
- WHEN core evaluation runs
- THEN `7.3.storage.localvolume` status is NOT_APPLICABLE

#### Scenario: FileIntegrity not found
- GIVEN `09_security/fileintegrity.json` is `_hc_not_found` or has empty items
- WHEN core evaluation runs
- THEN `7.7.file_integrity` status is NOT_APPLICABLE

### Requirement: PDB empty list is INFO
Native `7.5.pdb` SHALL be SKIPPED when the PDB capture envelope is missing or collection set `_hc_error`. An empty items list SHALL be INFO, not FAIL. A PDB with `status.disruptionsAllowed==0` and `currentHealthy < desiredHealthy` SHALL be WARNING; otherwise PASS. There SHALL NOT be a second PDB check_id.

#### Scenario: PDB list empty
- GIVEN `07_cluster_health/pdb.json` has `items` equal to `[]`
- WHEN the check runs
- THEN status is INFO

#### Scenario: PDB envelope missing
- GIVEN PDB is not in the collection
- WHEN the check runs
- THEN status is SKIPPED

#### Scenario: PDB collection error
- GIVEN PDB JSON has `_hc_error`
- WHEN the check runs
- THEN status is SKIPPED

### Requirement: Core profile emits mapped CCX CVE IDs
Core evaluation SHALL emit the mapped CVE/external CCX check IDs. When `12_ccx/ccx_rules.json` has no matching title or id, status SHALL be SKIPPED. When a payload row matches, status SHALL come from that row. `source` SHALL be `ccx`. There SHALL NOT be a second check_id for DNS pods, IPsec, or FeatureGate.

#### Scenario: CCX CVE without Insights payload
- GIVEN no matching row in `12_ccx/ccx_rules.json`
- WHEN core evaluation runs
- THEN each mapped CVE/external ID is emitted
- AND status is SKIPPED
- AND `source` is `ccx`

#### Scenario: CCX CVE with payload status
- GIVEN a `12_ccx/ccx_rules.json` row whose title or id matches a mapped CVE ID
- WHEN core evaluation runs
- THEN that check uses the runtime status from the payload
- AND `source` is `ccx`

### Requirement: Insights CCX CVE ingest bars
Core `evaluate_ccx` SHALL emit a row for each id in `CCX_STATIC_CHECK_IDS`. When InsightsOperator reporting is disabled (`spec.disabled`, `status.disabled`, or `spec.disableInsightsReporting` is true), each of those rows SHALL be `NOT_APPLICABLE`. Else when `12_ccx/ccx_rules` is missing, `_hc_not_found`, or `_hc_error`, each unmatched row SHALL be `SKIPPED` and evidence SHALL name `HC_CCX_RULES_FILE` and Insights Available. Else when a payload row matches a CVE, status SHALL follow the existing `_status` mapping of that payload. Else unmatched CVE ids SHALL be `SKIPPED`. Missing `HC_CCX_RULES_FILE` SHALL never FAIL. Evaluation SHALL NOT scrape Insights/Advisor HTTP APIs.

#### Scenario: disabled InsightsOperator is NOT_APPLICABLE
- GIVEN InsightsOperator with `spec.disabled` true
- WHEN `evaluate_ccx` runs
- THEN each `CCX_STATIC_CHECK_IDS` status is `NOT_APPLICABLE`
- AND the status is not `FAIL`

#### Scenario: missing rules file is SKIPPED
- GIVEN InsightsOperator reporting is not disabled
- AND `12_ccx/ccx_rules` has `_hc_not_found`
- WHEN `evaluate_ccx` runs
- THEN each `CCX_STATIC_CHECK_IDS` status is `SKIPPED`
- AND evidence contains `HC_CCX_RULES_FILE`
- AND the status is not `FAIL`

#### Scenario: matched payload keeps mapped status
- GIVEN a `ccx_rules` payload whose title matches `CVE-2026-31431`
- AND payload `status` is `PASS`
- WHEN `evaluate_ccx` runs
- THEN `7.7.ccx_external.cve_2026_31431_copy_fail_in_algif_aead` status is `PASS`
- AND the status is not `SKIPPED`

#### Scenario: unmatched CVE is not FAIL
- GIVEN a `ccx_rules` payload that does not mention the static CVE ids
- WHEN `evaluate_ccx` runs
- THEN each unmatched `CCX_STATIC_CHECK_IDS` status is `SKIPPED`
- AND the status is not `FAIL`

### Requirement: Node-roles missing-label scoring stays independent of taints
Core evaluation SHALL emit `7.5.node_roles`. The check SHALL FAIL when any node has an empty `node_roles(labels)` set (no `node-role.kubernetes.io/*` labels). The check SHALL PASS when every node has at least one role label. Payload missing SHALL remain SKIPPED (current engine status). `7.5.master_taints` SHALL remain independently scored. `7.5.node_roles` SHALL NOT absorb taint or compact-NoSchedule logic.

#### Scenario: unlabeled node fails node_roles
- GIVEN a node with no `node-role.kubernetes.io/*` labels
- WHEN core evaluation runs
- THEN `7.5.node_roles` status is FAIL

#### Scenario: every node has a role label
- GIVEN every node has at least one `node-role.kubernetes.io/*` label
- WHEN core evaluation runs
- THEN `7.5.node_roles` status is PASS

#### Scenario: master_taints is not folded into node_roles
- GIVEN a compact cluster with master NoSchedule taints
- WHEN core evaluation runs
- THEN `7.5.master_taints` is still emitted
- AND `7.5.node_roles` scoring does not use taint presence as its FAIL bar

### Requirement: Sparse TSR alias for ORIG node-role values
KB row `7.5.tsr.5_6_node_role_values` SHALL be a sparse alias (`content_from` exact `7.5.node_roles`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: node-role TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.5.tsr.5_6_node_role_values` is loaded
- THEN `content_from` is `7.5.node_roles`
- AND `include_in_findings` is false

### Requirement: Native node image garbage-collection aggregate
Core evaluation SHALL emit `7.6.node.image_gc`. Per member, `high_percent` SHALL be the collected `configz` `imageGCHighThresholdPercent` when present, else the named constant `IMAGE_GC_HIGH_DEFAULT_PERCENT` (85). Early warning SHALL use the named constant `IMAGE_GC_EARLY_WARNING_PERCENT` (50). FAIL when any member with numeric `used_percent` has `used_percent >= high_percent`. Else WARNING when any such member has `used_percent >= 50`. PASS when all scored members have `used_percent < 50`. INFO when the document is missing or has `_hc_error` at the root, or when no member has numeric `used_percent`. A member with missing `stats/summary` SHALL be omitted from FAIL and WARNING. `scoring_basis` SHALL be `doc_backed` on image_gc FAIL only. There SHALL be no per-node check_ids in this change.

#### Scenario: used percent at HIGH fails
- GIVEN a member with numeric `used_percent` equal to `high_percent` (including default 85)
- WHEN core evaluation runs
- THEN `7.6.node.image_gc` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: used percent at early warning
- GIVEN no member at or above HIGH
- AND at least one member with `used_percent` equal to 50 and `high_percent` equal to 85
- WHEN core evaluation runs
- THEN `7.6.node.image_gc` status is WARNING

#### Scenario: all scored members below 50
- GIVEN every member with numeric `used_percent` is below 50
- WHEN core evaluation runs
- THEN `7.6.node.image_gc` status is PASS

#### Scenario: all stats missing is INFO
- GIVEN every member has `_hc_error` true and no numeric `used_percent`
- WHEN core evaluation runs
- THEN `7.6.node.image_gc` status is INFO

### Requirement: Sparse TSR alias for ORIG node garbage collection
KB row `7.6.tsr.6_1_5_5_node_garbage_collection` SHALL be a sparse alias (`content_from` exact `7.6.node.image_gc`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: GC TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_5_5_node_garbage_collection` is loaded
- THEN `content_from` is `7.6.node.image_gc`
- AND `include_in_findings` is false

### Requirement: Live-only node image GC collect
Live collect MAY write `node_image_gc` under `08_day2`. Supportshell MAY omit that file. Supportshell SHALL NOT call node proxy `configz` or `stats/summary`. Collect SHALL NOT persist full kubelet `configz` or `stats/summary` documents; results SHALL contain counts, bytes, percents, and the `system_reserved_memory` / `auto_sizing_reserved` excerpts only.

#### Scenario: supportshell omits live-only GC file
- GIVEN supportshell `08_day2.sh`
- WHEN an operator runs must-gather collect
- THEN `node_image_gc` is not produced via node proxy

#### Scenario: collect does not dump raw proxy bodies
- GIVEN live `hc_node_image_gc_stats`
- WHEN `node_image_gc.json` is written
- THEN the file does not contain a full `configz` or `stats/summary` document

### Requirement: Native effective kubelet systemReserved scoring
Core evaluation SHALL emit `7.2.kubelet.system_reserved` with title `Effective kubelet systemReserved`. The engine SHALL read `results["08_day2"]["node_image_gc"]` members and `category_data` nodes. Per member, `system_reserved_memory` and `auto_sizing_reserved` SHALL come from kubeletconfig excerpts only. `_hc_error` with empty members SHALL be SKIPPED. Zero members SHALL be NOT_APPLICABLE. Any member missing reserved memory and not `auto_sizing_reserved` true SHALL be WARNING. Else any node with capacity ≥64 GiB whose reserved memory is exactly `1Gi` or `1G` SHALL be INFO. Else PASS. The check SHALL NOT FAIL. `_check_system_reserved` / `7.2.node.*.sysreserved` bars SHALL not change. Raw configz SHALL not be written to `hc_results`.

#### Scenario: default 1Gi on large node is INFO
- GIVEN a `node_image_gc` member with `system_reserved_memory` `1Gi`
- AND the matching node capacity is ≥64 GiB
- AND no member is missing reserved memory without auto-size
- WHEN core evaluation runs
- THEN `7.2.kubelet.system_reserved` status is INFO
- AND the status is not WARNING or FAIL

#### Scenario: 2Gi reserved is PASS
- GIVEN every member has parseable reserved memory `2Gi`
- AND no member hits the 1Gi-on-≥64-GiB bar
- WHEN core evaluation runs
- THEN `7.2.kubelet.system_reserved` status is PASS
- AND the status is not INFO

#### Scenario: missing reserved memory is WARNING
- GIVEN a member with empty `system_reserved_memory`
- AND `auto_sizing_reserved` is not true
- WHEN core evaluation runs
- THEN `7.2.kubelet.system_reserved` status is WARNING
- AND the status is not PASS

#### Scenario: per-node sysreserved bars stay CR-based
- GIVEN a node with ≥64 GiB RAM and no matching KubeletConfig `systemReserved`
- WHEN `_check_system_reserved` runs
- THEN that node's `7.2.node.*.sysreserved` status is WARNING

### Requirement: Native keepalived VIP pod scoring
Core evaluation SHALL emit `7.2.topo.keepalived` with title `Keepalived VIP pods`. The engine SHALL read `results["07_cluster_health"]["pods_all"]`. A keepalived pod SHALL be a pod whose namespace is `openshift-kni-infra` and whose `metadata.name` starts with `keepalived-`. Missing or `_hc_error` `pods_all` SHALL be SKIPPED. Zero matching pods SHALL be INFO. Any matching pod whose `status.phase` is not `Running` or whose `containerStatuses` are missing or not all `ready` true SHALL be FAIL. Else PASS. The engine SHALL NOT scrape VRRP config. The engine SHALL NOT retune `7.2.topo.haproxy_ha`.

#### Scenario: Ready keepalived pods are PASS
- GIVEN `pods_all` contains keepalived pods in `openshift-kni-infra`
- AND every matching pod phase is Running
- AND every matching pod container is Ready
- WHEN core evaluation runs
- THEN `7.2.topo.keepalived` status is PASS

#### Scenario: not Ready keepalived is FAIL
- GIVEN a keepalived pod in `openshift-kni-infra` whose phase is not Running or whose containers are not all Ready
- WHEN core evaluation runs
- THEN `7.2.topo.keepalived` status is FAIL

#### Scenario: zero keepalived pods is INFO
- GIVEN `pods_all` is present and not `_hc_error`
- AND no pod matches namespace `openshift-kni-infra` with name prefix `keepalived-`
- WHEN core evaluation runs
- THEN `7.2.topo.keepalived` status is INFO
- AND the status is not FAIL

### Requirement: HAProxy TSR stays on replica native
KB row `7.2.tsr.2_2_3_haproxy_ha` SHALL keep `content_from` exact `7.2.topo.haproxy_ha`. The row SHALL NOT use `content_from` `7.2.topo.keepalived`.

#### Scenario: HAProxy TSR is not retargeted
- GIVEN production `load_kb()`
- WHEN entry `7.2.tsr.2_2_3_haproxy_ha` is loaded
- THEN `content_from` is `7.2.topo.haproxy_ha`

### Requirement: Native CNV NNCP and NNCE health
Core evaluation SHALL emit `7.4.cnv.nncp`. The check SHALL be NOT_APPLICABLE when both NNCP and NNCE payloads are missing. Else the check SHALL be INFO when both item lists are empty. The check SHALL FAIL when any NNCP or NNCE item is not healthy. An item SHALL be healthy when `_find_condition` on `status.conditions` has `Available` status `True` or `SuccessfullyConfigured` status `True`. Else the check SHALL PASS when at least one item exists and every item is healthy. `scoring_basis` SHALL be `doc_backed` on NNCP FAIL. The check SHALL NOT score NAD count. The check SHALL NOT gate on CNV presence. `7.3.net.hwnet` SHALL remain independently scored.

#### Scenario: both payloads missing is not applicable
- GIVEN NNCP and NNCE payloads that `_is_missing` treats as missing
- WHEN core evaluation runs
- THEN `7.4.cnv.nncp` status is NOT_APPLICABLE

#### Scenario: zero policies is INFO
- GIVEN NNCP and NNCE payloads present with empty `items` lists
- WHEN core evaluation runs
- THEN `7.4.cnv.nncp` status is INFO

#### Scenario: degraded enactment fails
- GIVEN at least one NNCE item whose `Available` condition is not True and `SuccessfullyConfigured` is not True
- WHEN core evaluation runs
- THEN `7.4.cnv.nncp` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: all items healthy pass
- GIVEN at least one NNCP or NNCE item
- AND every item has `Available` True or `SuccessfullyConfigured` True
- WHEN core evaluation runs
- THEN `7.4.cnv.nncp` status is PASS

### Requirement: Native virt-default StorageClass
Core evaluation SHALL emit `7.4.cnv.virt_storageclass`. The native identifier SHALL NOT contain `node_disk`. TSR check_id `7.4.tsr.4_8_1_3_4_node_disk` MAY remain as an alias source. The check SHALL be NOT_APPLICABLE when HyperConverged is missing. The check SHALL be SKIPPED when CNV is present and the StorageClass payload is missing. Else the check SHALL PASS when exactly one StorageClass has annotation `storageclass.kubevirt.io/is-default-virt-class` equal to `"true"`. Else the check SHALL FAIL. VolumeSnapshotClass MAY appear in evidence and SHALL NOT change PASS/FAIL. The check SHALL NOT use cluster annotation `is-default-class`. `scoring_basis` SHALL be `doc_backed` on virt-default FAIL. `7.3.storage.default_sc` SHALL remain independently scored.

#### Scenario: CNV missing is not applicable
- GIVEN HyperConverged `_hc_not_found` or `_is_missing`
- WHEN core evaluation runs
- THEN `7.4.cnv.virt_storageclass` status is NOT_APPLICABLE

#### Scenario: CNV present and zero virt-default fails
- GIVEN HyperConverged present
- AND zero StorageClasses with virt-default annotation `"true"`
- WHEN core evaluation runs
- THEN `7.4.cnv.virt_storageclass` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: exactly one virt-default passes
- GIVEN HyperConverged present
- AND exactly one StorageClass with annotation `storageclass.kubevirt.io/is-default-virt-class` equal to `"true"`
- WHEN core evaluation runs
- THEN `7.4.cnv.virt_storageclass` status is PASS

### Requirement: Native OADP CSV DPA BSL state
Core evaluation SHALL emit `7.4.oadp.state`. The check SHALL be NOT_APPLICABLE when there are no CSV items, no DPA items, and no BackupStorageLocation items. The check SHALL FAIL when any CSV item in namespace `openshift-adp` has `status.phase` not equal to `Succeeded`, or any DPA is not Available (`Available=True`), or any BackupStorageLocation has `status.phase` not equal to `Available`. Else the check SHALL PASS. Absence SHALL NOT FAIL. Inventory check `7.4.OADP` SHALL remain independently scored.

#### Scenario: no OADP resources is not applicable
- GIVEN DPA, CSV, and BackupStorageLocation payloads with no items
- WHEN core evaluation runs
- THEN `7.4.oadp.state` status is NOT_APPLICABLE

#### Scenario: CSV not Succeeded fails
- GIVEN a CSV item in `openshift-adp` with `status.phase` equal to `Failed`
- WHEN core evaluation runs
- THEN `7.4.oadp.state` status is FAIL

#### Scenario: DPA and BSL healthy pass
- GIVEN at least one CSV, DPA, or BackupStorageLocation item
- AND every `openshift-adp` CSV phase is Succeeded
- AND every DPA is Available
- AND every BackupStorageLocation phase is Available
- WHEN core evaluation runs
- THEN `7.4.oadp.state` status is PASS

### Requirement: Native Quay application pod scoring
Core evaluation SHALL emit `7.4.quay.pods` with title `Internal Quay application pods`. The engine SHALL read `results["06_layered"]["quay_registry"]` and `results["06_layered"]["quay_pods"]`. Registry namespaces SHALL be the unique `metadata.namespace` of each QuayRegistry item plus `spec.targetNamespace` when present. A matching application pod SHALL be a pod whose `metadata.name` contains `quay-app` or `registry-quay-app`. Running SHALL mean `status.phase` is `Running` and every `containerStatuses` entry has `ready` true. Missing or `_hc_error` or `_hc_not_found` `quay_pods` SHALL be SKIPPED. Zero QuayRegistry items SHALL be NOT_APPLICABLE. Any registry namespace with zero matching Running pods SHALL be FAIL. Else PASS. The engine SHALL NOT score QuayRegistry Available as a substitute. The engine SHALL NOT retune `_evaluate_layered_product` for Quay Registry.

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

### Requirement: Sparse TSR aliases for ORIG virt leaves
KB rows `7.4.tsr.4_8_2_2_1_2_network_configuration`, `7.4.tsr.4_8_1_3_4_node_disk`, and `7.4.tsr.4_8_5_3_1_oadp_operator` SHALL be sparse aliases (`content_from` to the matching native, `include_in_findings = false`). Alias targets SHALL be `7.4.cnv.nncp`, `7.4.cnv.virt_storageclass`, and `7.4.oadp.state` respectively. Alias rows SHALL NOT overlay inherited narrative keys. `7.4.tsr.4_8_1_4_node_disk` SHALL remain `content_from` exact `7.4.cnv.state`.

#### Scenario: virt-default TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_1_3_4_node_disk` is loaded
- THEN `content_from` is `7.4.cnv.virt_storageclass`
- AND `include_in_findings` is false

#### Scenario: parent node_disk section stays on cnv.state
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_1_4_node_disk` is loaded
- THEN `content_from` is `7.4.cnv.state`

### Requirement: Collect MAY write virt leaf evidence
Live and supportshell collect MAY write `nnce` and `volumesnapshotclass` under `05_components`. Live and supportshell collect MAY write `oadp_dpa`, `oadp_csv`, and `backupstoragelocation` under `06_layered`.

#### Scenario: collect names for virt leaves
- GIVEN live `05_components.sh` and `06_layered.sh`
- WHEN an operator inspects capture stems
- THEN `nnce`, `volumesnapshotclass`, `oadp_dpa`, `oadp_csv`, and `backupstoragelocation` are present as capture names

### Requirement: Native CNV related subscriptions
Core evaluation SHALL emit `7.4.cnv.subscription`. The check SHALL be NOT_APPLICABLE when HyperConverged is missing. Else the check SHALL FAIL when no subscription in namespace `openshift-cnv` has `metadata.name` or `spec.name` equal to `kubevirt-hyperconverged` with `status.state` `AtLatestKnown` and `status.installedCSV` equal to `status.currentCSV`. Else the check SHALL PASS. The check SHALL NOT dump onto `7.4.cnv.state`.

#### Scenario: stalled subscription fails
- GIVEN HyperConverged present
- AND a kubevirt-hyperconverged subscription in `openshift-cnv` whose state is not `AtLatestKnown`
- WHEN core evaluation runs
- THEN `7.4.cnv.subscription` status is FAIL

#### Scenario: HyperConverged missing is not applicable
- GIVEN HyperConverged `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.4.cnv.subscription` status is NOT_APPLICABLE

### Requirement: Native optional NMState and SR-IOV CSV
Core evaluation SHALL emit `7.4.cnv.nmstate_csv` and `7.4.cnv.sriov_csv`. Zero CSV items in `openshift-nmstate` or `openshift-sriov-network-operator` respectively SHALL be NOT_APPLICABLE. Any CSV in that namespace whose `status.phase` is not `Succeeded` SHALL FAIL. Else the check SHALL PASS. Missing operator SHALL NOT FAIL. The check SHALL NOT score NNCE or SriovNetworkNodePolicy.

#### Scenario: empty NMState namespace is not applicable
- GIVEN no CSV items in namespace `openshift-nmstate`
- WHEN core evaluation runs
- THEN `7.4.cnv.nmstate_csv` status is NOT_APPLICABLE

#### Scenario: failed SR-IOV CSV fails
- GIVEN a CSV in `openshift-sriov-network-operator` with phase `Failed`
- WHEN core evaluation runs
- THEN `7.4.cnv.sriov_csv` status is FAIL

### Requirement: Native VM runStrategy
Core evaluation SHALL emit `7.4.cnv.run_strategy`. HyperConverged missing or VM payload missing SHALL be SKIPPED. Zero VM items SHALL be NOT_APPLICABLE. Any VM whose `spec.runStrategy` is not exactly `Always` SHALL be INFO. All `Always` SHALL PASS. The check SHALL NEVER FAIL.

#### Scenario: Manual runStrategy is INFO
- GIVEN HyperConverged present
- AND a VM whose `spec.runStrategy` is not `Always`
- WHEN core evaluation runs
- THEN `7.4.cnv.run_strategy` status is INFO

### Requirement: Native VMI phase without PromQL
Core evaluation SHALL emit `7.4.cnv.vmi_phase` from `cnv_vmi` `.status.phase`. Missing VMI payload SHALL be SKIPPED. Zero items SHALL be NOT_APPLICABLE. Any phase in Pending, Scheduling, Failed, or Unknown SHALL be WARNING. Else PASS. The check SHALL NOT use PromQL.

#### Scenario: Failed VMI is WARNING
- GIVEN a VMI with phase `Failed`
- WHEN core evaluation runs
- THEN `7.4.cnv.vmi_phase` status is WARNING

### Requirement: Native live-migration network
Core evaluation SHALL emit `7.4.cnv.migration_network`. HyperConverged missing SHALL be NOT_APPLICABLE. Missing, empty, or `<none>` `spec.liveMigrationConfig.network` SHALL PASS. A named network SHALL FAIL unless some NetworkAttachmentDefinition has `metadata.name` equal to that string and `metadata.namespace` equal to `openshift-cnv`. The check SHALL NOT alias to `7.4.cnv.live_migratable`.

#### Scenario: named network without NAD fails
- GIVEN HyperConverged with a named live-migration network
- AND no matching NAD in `openshift-cnv`
- WHEN core evaluation runs
- THEN `7.4.cnv.migration_network` status is FAIL

### Requirement: Native Linux-bridge NAD inventory
Core evaluation SHALL emit `7.4.cnv.linux_bridge`. Missing NAD payload SHALL be SKIPPED. Zero items whose CNI `type` is `cnv-bridge` or `bridge` SHALL be INFO. Else PASS. Invalid `spec.config` JSON SHALL skip that item and SHALL NOT FAIL. Empty NAD lists SHALL NOT FAIL. The check SHALL NOT dump onto `7.4.cnv.nncp`.

#### Scenario: no bridge-type NAD is INFO
- GIVEN NAD payload present with no `cnv-bridge` or `bridge` CNI type
- WHEN core evaluation runs
- THEN `7.4.cnv.linux_bridge` status is INFO

### Requirement: Native CNV node placement
Core evaluation SHALL emit `7.4.cnv.node_placement`. HyperConverged missing SHALL be NOT_APPLICABLE. virt-handler DaemonSet missing SHALL be SKIPPED. `status.numberReady` not equal to `status.desiredNumberScheduled` SHALL FAIL. Else WARNING if any non-control-plane node lacks label `kubevirt.io/schedulable` equal to `"true"`. Control-plane is `node-role.kubernetes.io/control-plane` or `node-role.kubernetes.io/master` present. Zero non-control-plane nodes SHALL PASS after a ready DaemonSet. Empty HyperConverged `nodePlacement` SHALL NOT FAIL. The check SHALL NOT score CPU `vmx`/`svm` labels.

#### Scenario: handler not ready fails
- GIVEN HyperConverged present
- AND virt-handler `numberReady` not equal to `desiredNumberScheduled`
- WHEN core evaluation runs
- THEN `7.4.cnv.node_placement` status is FAIL

#### Scenario: unschedulable worker is WARNING
- GIVEN virt-handler ready equals desired
- AND a non-control-plane node without `kubevirt.io/schedulable` equal to `"true"`
- WHEN core evaluation runs
- THEN `7.4.cnv.node_placement` status is WARNING

### Requirement: Native CDI image upload
Core evaluation SHALL emit `7.4.cnv.cdi`. Missing CDI SHALL be NOT_APPLICABLE. Conditions not (`Available=True` and `Progressing=False` and `Degraded=False`) SHALL FAIL. Else WARNING if no `cnv_pods` item with label `app=cdi-uploadproxy` or any such pod is not Ready. Else PASS. The check SHALL NOT dump onto `7.4.cnv.pods`.

#### Scenario: missing CDI is not applicable
- GIVEN CDI `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.4.cnv.cdi` status is NOT_APPLICABLE

#### Scenario: degraded CDI fails
- GIVEN CDI `Degraded=True`
- WHEN core evaluation runs
- THEN `7.4.cnv.cdi` status is FAIL

### Requirement: Native CDI StorageProfile clone strategy
Core evaluation SHALL emit `7.4.cnv.storageprofile`. Missing StorageProfile payload (`_is_missing`) SHALL be NOT_APPLICABLE. Zero items SHALL be INFO. Any item whose `status.cloneStrategy` equals `copy` SHALL be WARNING. Else the check SHALL PASS. The check SHALL read `status.cloneStrategy` only; `spec.cloneStrategy` and snapshotClass SHALL be evidence only. The check SHALL NOT alias to `7.4.cnv.virt_storageclass`. The check SHALL NOT retune virt-default StorageClass scoring.

#### Scenario: cloneStrategy copy is WARNING
- GIVEN a StorageProfile item whose `status.cloneStrategy` is `copy`
- WHEN core evaluation runs
- THEN `7.4.cnv.storageprofile` status is WARNING

#### Scenario: zero StorageProfile items is INFO
- GIVEN StorageProfile payload present with zero items
- WHEN core evaluation runs
- THEN `7.4.cnv.storageprofile` status is INFO

### Requirement: Native CNV VM-namespace ResourceQuota
Core evaluation SHALL emit `7.4.cnv.vm_quota`. HyperConverged missing SHALL be NOT_APPLICABLE. Zero VirtualMachine items SHALL be NOT_APPLICABLE. VM namespaces SHALL be the unique `metadata.namespace` values on VM items. If any VM namespace has zero ResourceQuota items SHALL be INFO. Else if any ResourceQuota in those namespaces has a key present in both `status.used` and `spec.hard` with equal string values SHALL be WARNING. Else the check SHALL PASS. `spec.hard` and `status.used` that are not dicts SHALL skip that quota for the exhausted check. The check SHALL NEVER FAIL. Missing ResourceQuota in a VM namespace SHALL NOT FAIL. The check SHALL NOT alias to `7.6.rq` or `7.6.cluster_quota`. The check SHALL NOT import or call `_evaluate_resource_quotas`.

#### Scenario: VM namespace without ResourceQuota is INFO
- GIVEN HyperConverged present
- AND at least one VirtualMachine
- AND that VM namespace has zero ResourceQuota items
- WHEN core evaluation runs
- THEN `7.4.cnv.vm_quota` status is INFO

#### Scenario: used equals hard is WARNING
- GIVEN every VM namespace has at least one ResourceQuota
- AND a ResourceQuota in a VM namespace has a shared key whose `status.used` string equals `spec.hard` string
- WHEN core evaluation runs
- THEN `7.4.cnv.vm_quota` status is WARNING

### Requirement: Native virt CPU flags from kubevirt labels
Core evaluation SHALL emit `7.4.cnv.cpu_virt_flag`. HyperConverged missing (`_is_missing` or `_hc_not_found`) SHALL be NOT_APPLICABLE. Nodes payload `_hc_error` SHALL be SKIPPED. A matching node SHALL be a schedulable node (`spec.unschedulable` is not true) whose labels include `cpu-feature.node.kubevirt.io/vmx` equal to `true` or `cpu-feature.node.kubevirt.io/svm` equal to `true`. Zero matching nodes SHALL be WARNING. Else the check SHALL PASS. The check SHALL NEVER FAIL. The check SHALL NOT require both vmx and svm. The check SHALL NOT read `/proc/cpuinfo`. The check SHALL NOT retarget `7.4.tsr.4_8_1_3_2_node_cpu`.

#### Scenario: svm label is PASS
- GIVEN HyperConverged present
- AND a schedulable node with label `cpu-feature.node.kubevirt.io/svm` equal to `true`
- WHEN core evaluation runs
- THEN `7.4.cnv.cpu_virt_flag` status is PASS

#### Scenario: no vmx or svm labels is WARNING
- GIVEN HyperConverged present
- AND nodes present without vmx or svm equal to `true`
- WHEN core evaluation runs
- THEN `7.4.cnv.cpu_virt_flag` status is WARNING

#### Scenario: HyperConverged missing is not applicable
- GIVEN HyperConverged `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.4.cnv.cpu_virt_flag` status is NOT_APPLICABLE

#### Scenario: nodes error is SKIPPED
- GIVEN HyperConverged present
- AND nodes payload `_hc_error`
- WHEN core evaluation runs
- THEN `7.4.cnv.cpu_virt_flag` status is SKIPPED

### Requirement: Node CPU TSR stays on CNV state
KB row `7.4.tsr.4_8_1_3_2_node_cpu` SHALL keep `content_from` exact `7.4.cnv.state`. The row SHALL NOT use `content_from` `7.4.cnv.cpu_virt_flag`.

#### Scenario: node_cpu TSR is not retargeted
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_1_3_2_node_cpu` is loaded
- THEN `content_from` is `7.4.cnv.state`

### Requirement: Sparse TSR aliases for virt P3
KB rows SHALL sparse-alias (`include_in_findings = false`): `7.4.tsr.4_8_1_1_2_related_subscriptions` → `7.4.cnv.subscription`; `7.4.tsr.4_8_1_5_1_1_cnv_operators_node_placement` → `7.4.cnv.node_placement`; `7.4.tsr.4_8_1_5_1_5_vm_run_strategy_and_availability` → `7.4.cnv.run_strategy`; `7.4.tsr.4_8_2_1_1_3_live_migration_network_readiness` → `7.4.cnv.migration_network`; `7.4.tsr.4_8_3_2_1_nmstate_operator` → `7.4.cnv.nmstate_csv`; `7.4.tsr.4_8_3_2_2_sr_iov_operator` → `7.4.cnv.sriov_csv`; `7.4.tsr.4_8_3_2_3_linux_bridge_network` → `7.4.cnv.linux_bridge`; `7.4.tsr.4_8_5_2_3_cnv_vmi_readiness_prometheus` → `7.4.cnv.vmi_phase`; `7.4.tsr.4_8_5_3_5_cdi_image_upload_posture` → `7.4.cnv.cdi`; `7.4.tsr.4_8_3_1_1_storage_profiles` → `7.4.cnv.storageprofile`; `7.4.tsr.4_8_5_1_1_quota_and_resources` → `7.4.cnv.vm_quota`. Alias rows SHALL NOT overlay inherited narrative keys. `7.4.tsr.4_8_5_1_1_quota_and_resources` SHALL NOT have `content_from` equal to `7.6.rq`. `7.4.tsr.4_8_3_1_1_storage_profiles` SHALL NOT have `content_from` equal to `7.4.cnv.virt_storageclass`. IN leaves SHALL NOT alias to `7.4.cnv.state`, `7.4.cnv.nncp`, `7.4.cnv.live_migratable`, or `7.4.cnv.pods`.

#### Scenario: related subscriptions TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_1_1_2_related_subscriptions` is loaded
- THEN `content_from` is `7.4.cnv.subscription`
- AND `include_in_findings` is false

#### Scenario: storage profiles TSR aliases the native
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_3_1_1_storage_profiles` is loaded
- THEN `content_from` is `7.4.cnv.storageprofile`
- AND `include_in_findings` is false

#### Scenario: quota TSR aliases vm_quota not 7.6.rq
- GIVEN production `load_kb()`
- WHEN entry `7.4.tsr.4_8_5_1_1_quota_and_resources` is loaded
- THEN `content_from` is `7.4.cnv.vm_quota`
- AND `content_from` is not `7.6.rq`
- AND `include_in_findings` is false

### Requirement: Collect MAY write CNV P3 evidence
Live and supportshell collect MAY write `cnv_cdi` and `cnv_virt_handler_ds` under `06_layered`. Collect MAY write `cnv_vm` and `cnv_vmi` under `06_layered`.

#### Scenario: collect names for CNV P3
- GIVEN live `06_layered.sh`
- WHEN an operator inspects capture stems
- THEN `cnv_cdi`, `cnv_virt_handler_ds`, `cnv_vm`, and `cnv_vmi` are present as capture names

### Requirement: Collect MAY write StorageProfile
Live and supportshell collect MAY write `storageprofile` under `05_components` using `oc get storageprofile || true`. Collect SHALL NOT add a new ResourceQuota capture for this native.

#### Scenario: collect name for StorageProfile
- GIVEN live `05_components.sh`
- WHEN an operator inspects capture stems
- THEN `storageprofile` is present as a capture name

### Requirement: Native registry storage scoring
Core evaluation SHALL emit `7.3.registry.storage`. The check SHALL FAIL when `spec.managementState` is Managed or Unmanaged and the storage backend (first `spec.storage` key other than `managementState`) is `emptyDir`. The check SHALL PASS when that backend is object storage (`s3`, `azure`, `gcs`, `ibmcos`, `oss`, `swift`) or `pvc`. The check SHALL be INFO when the registry payload is missing or has `_hc_error`, or when `managementState` is Removed. An unknown remaining storage key SHALL be WARNING, not FAIL. `scoring_basis` SHALL be `doc_backed` on emptyDir FAIL only. `7.3.registry.state` SHALL remain independently scored. Registry PVC access mode and file provisioner SHALL NOT be scored.

#### Scenario: emptyDir under Managed fails
- GIVEN Image Registry Operator `managementState` is Managed
- AND `spec.storage.emptyDir` is the storage backend
- WHEN core evaluation runs
- THEN `7.3.registry.storage` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: Removed is informational
- GIVEN Image Registry Operator `managementState` is Removed
- WHEN core evaluation runs
- THEN `7.3.registry.storage` status is INFO

#### Scenario: object or PVC backend passes
- GIVEN `managementState` is Managed
- AND the storage backend is `s3` or `pvc`
- WHEN core evaluation runs
- THEN `7.3.registry.storage` status is PASS

#### Scenario: unknown storage key is warning
- GIVEN `managementState` is Managed
- AND the remaining storage key is neither emptyDir, pvc, nor a listed object backend
- WHEN core evaluation runs
- THEN `7.3.registry.storage` status is WARNING
- AND the status is not FAIL

#### Scenario: registry.state stays independent
- GIVEN a scored registry payload
- WHEN core evaluation runs
- THEN `7.3.registry.state` is still emitted
- AND `7.3.registry.storage` does not replace its scoring

### Requirement: Native monitoring storage scoring
Core evaluation SHALL emit `7.3.monitoring.storage`. The check SHALL FAIL when any Prometheus or Alertmanager item lacks `spec.storage.volumeClaimTemplate`. The check SHALL WARNING when a template is present and any access mode is `ReadWriteMany` or the resolved StorageClass provisioner contains `nfs`, `efs`, `azurefile`, or `cephfs`. The check SHALL PASS when every item has a template and RWO (or empty class name equal to the default StorageClass) on a non-file provisioner. Empty class name with a template and no default StorageClass SHALL PASS on access mode only. The check SHALL be INFO when Prometheus and Alertmanager payloads are both missing. FAIL SHALL win over WARNING. `scoring_basis` SHALL be `doc_backed` on missing-template FAIL only. `7.3.monitoring.config` SHALL remain independently scored.

#### Scenario: missing volumeClaimTemplate fails
- GIVEN a Prometheus or Alertmanager item with no `spec.storage.volumeClaimTemplate`
- WHEN core evaluation runs
- THEN `7.3.monitoring.storage` status is FAIL
- AND `scoring_basis` is `doc_backed`

#### Scenario: ReadWriteMany warns
- GIVEN every scored item has a volumeClaimTemplate
- AND at least one access mode is `ReadWriteMany`
- WHEN core evaluation runs
- THEN `7.3.monitoring.storage` status is WARNING

#### Scenario: RWO block passes
- GIVEN every scored item has a volumeClaimTemplate
- AND access modes are not `ReadWriteMany`
- AND the resolved provisioner is not file (`nfs` / `efs` / `azurefile` / `cephfs`)
- WHEN core evaluation runs
- THEN `7.3.monitoring.storage` status is PASS

#### Scenario: both monitoring payloads missing is informational
- GIVEN Prometheus and Alertmanager payloads are missing or `_hc_error`
- WHEN core evaluation runs
- THEN `7.3.monitoring.storage` status is INFO

#### Scenario: monitoring.config stays independent
- GIVEN a scored cluster-monitoring-config ConfigMap
- WHEN core evaluation runs
- THEN `7.3.monitoring.config` is still emitted
- AND `7.3.monitoring.storage` does not replace its scoring

### Requirement: Sparse TSR aliases for ORIG storage stories
KB rows `7.3.tsr.3_6_2_registry_storage_type` and `7.3.tsr.3_7_2_monitoring_storage_type` SHALL be sparse aliases (`content_from` to the matching native, `include_in_findings = false`). Alias targets SHALL be `7.3.registry.storage` and `7.3.monitoring.storage` respectively. Alias rows SHALL NOT overlay inherited narrative keys. `7.3.tsr.3_6_2_registry_storage_type` SHALL NOT point at `7.3.tsr.3_6_1_registry_scaled`.

#### Scenario: registry storage TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_6_2_registry_storage_type` is loaded
- THEN `content_from` is `7.3.registry.storage`
- AND `include_in_findings` is false

#### Scenario: monitoring storage TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_7_2_monitoring_storage_type` is loaded
- THEN `content_from` is `7.3.monitoring.storage`
- AND `include_in_findings` is false

### Requirement: No new collect files for registry or monitoring storage
Collect SHALL NOT add new files for `7.3.registry.storage` or `7.3.monitoring.storage`. Scoring SHALL use existing `05_components` `imageregistry`, `prometheus`, `alertmanager`, and `storageclass` artifacts.

#### Scenario: collect files unchanged for these checks
- GIVEN live `05_components.sh`
- WHEN an operator runs collect
- THEN no additional gather is required to score registry or monitoring storage

### Requirement: Sparse TSR aliases for kubelet, pod restarts, and update history
KB row `7.5.tsr.5_1_node_kubelet_health` SHALL be a sparse alias (`content_from` exact `7.5.kubelet_health`, `include_in_findings = false`). KB row `7.5.tsr.5_5_pod_frequent_restarts` SHALL be a sparse alias (`content_from` exact `7.5.pod_restarts`, `include_in_findings = false`). KB row `7.6.tsr.6_2_1_update_history` SHALL be a sparse alias (`content_from` exact `7.6.upgrade.history`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: kubelet TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.5.tsr.5_1_node_kubelet_health` is loaded
- THEN `content_from` is `7.5.kubelet_health`
- AND `include_in_findings` is false

#### Scenario: pod-restarts TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.5.tsr.5_5_pod_frequent_restarts` is loaded
- THEN `content_from` is `7.5.pod_restarts`
- AND `include_in_findings` is false

#### Scenario: update-history TSR id is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_2_1_update_history` is loaded
- THEN `content_from` is `7.6.upgrade.history`
- AND `include_in_findings` is false

### Requirement: Native cluster node-utilization rollup
Core evaluation SHALL emit `7.5.node.utilization` after per-node `7.5.node.{short}.utilization` rows when `oc adm top nodes` parses to a non-empty per-node list. Status SHALL be WARNING if any per-node row is WARNING; else INFO if any per-node row is INFO; else PASS. Per-node check_ids SHALL remain. Missing, empty, or unparseable `top_nodes` SHALL emit NOT_APPLICABLE on `7.5.node.utilization` and SHALL keep existing `7.5.node_util` NOT_APPLICABLE. CPU percent WARNING SHALL remain greater than 80; memory percent WARNING SHALL remain greater than 85; INFO SHALL remain CPU greater than 60 or memory greater than 70. The rollup SHALL NOT FAIL. The rollup SHALL NOT re-parse CPU or memory percents.

#### Scenario: any per-node WARNING rolls up to WARNING
- GIVEN at least one per-node utilization row with status WARNING
- WHEN core evaluation runs
- THEN `7.5.node.utilization` status is WARNING
- AND per-node utilization check_ids are still emitted

#### Scenario: all per-node rows PASS
- GIVEN every per-node utilization row is PASS
- WHEN core evaluation runs
- THEN `7.5.node.utilization` status is PASS

#### Scenario: missing top_nodes is NOT_APPLICABLE on both ids
- GIVEN `top_nodes` is missing or `_hc_error`
- WHEN core evaluation runs
- THEN `7.5.node.utilization` status is NOT_APPLICABLE
- AND `7.5.node_util` status is NOT_APPLICABLE

### Requirement: Native volume mount p99 scoring
Core evaluation SHALL emit `7.5.volume.mount_p99`. The engine SHALL read `results["10_metrics"]["volume_mount_p99"]`. Missing payload or `_hc_error` SHALL be SKIPPED. A successful query whose result vector is empty SHALL be INFO. The scored value SHALL be the maximum finite numeric sample in the vector. NaN and Inf samples SHALL be ignored. A maximum greater than 10 seconds SHALL be FAIL. A maximum greater than 2 seconds and at most 10 seconds SHALL be WARNING. Else PASS. The engine SHALL NOT scrape host mount tables. The engine SHALL NOT retune PVC used-percent checks. The engine SHALL NOT emit `7.5.vol_mount`.

#### Scenario: p99 above 10 seconds is FAIL
- GIVEN `volume_mount_p99` has a successful Prometheus vector
- AND the maximum sample is greater than 10 seconds
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is FAIL

#### Scenario: p99 above 2 seconds is WARNING
- GIVEN `volume_mount_p99` has a successful Prometheus vector
- AND the maximum sample is greater than 2 seconds and at most 10 seconds
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is WARNING

#### Scenario: p99 at or below 2 seconds is PASS
- GIVEN `volume_mount_p99` has a successful Prometheus vector
- AND the maximum sample is at most 2 seconds
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is PASS

#### Scenario: empty result vector is INFO
- GIVEN `volume_mount_p99` is present and not `_hc_error`
- AND the Prometheus result vector is empty
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is INFO
- AND the status is not FAIL

#### Scenario: missing query is SKIPPED
- GIVEN `volume_mount_p99` is missing or `_hc_error`
- WHEN core evaluation runs
- THEN `7.5.volume.mount_p99` status is SKIPPED

### Requirement: TSR 5.10 aliases the native
KB row `7.5.tsr.5_10_volume_mount_durations` SHALL set `content_from` exact `7.5.volume.mount_p99`. The row SHALL set `include_in_findings` false.

#### Scenario: TSR 5.10 aliases native mount p99
- GIVEN production `load_kb()`
- WHEN entry `7.5.tsr.5_10_volume_mount_durations` is loaded
- THEN `content_from` is `7.5.volume.mount_p99`
- AND `include_in_findings` is false

### Requirement: Sparse TSR aliases for current node load
KB rows `7.6.tsr.6_1_3_1_current_node_load` and `7.6.tsr.6_1_3_node_load` SHALL be sparse aliases (`content_from` exact `7.5.node.utilization`, `include_in_findings = false`). There SHALL NOT be a `content_from` chain through `7.6.tsr.6_1_3_1_current_node_load`.

#### Scenario: node-load leaf and parent alias the rollup
- GIVEN production `load_kb()`
- WHEN entries `7.6.tsr.6_1_3_1_current_node_load` and `7.6.tsr.6_1_3_node_load` are loaded
- THEN each `content_from` is `7.5.node.utilization`
- AND each `include_in_findings` is false

### Requirement: Existing pruning hops hidden from Chapter 6
KB rows `7.6.tsr.6_1_5_1_pod_pruning`, `7.6.tsr.6_1_5_4_job_pruning`, `7.6.tsr.6_1_5_6_pruning_namespaces`, and `7.6.tsr.6_1_5_pruning` SHALL set `include_in_findings = false`.

#### Scenario: pruning hops are hidden from findings
- GIVEN production `load_kb()`
- WHEN those four pruning entries are loaded
- THEN each `include_in_findings` is false

### Requirement: Native user-project quota coverage scoring
Core evaluation SHALL emit `7.6.quota.coverage` with title `User project quota coverage`. Missing namespace, ResourceQuota, or LimitRange payload SHALL be SKIPPED. A namespace SHALL be a user namespace when its name does not start with `openshift-` or `kube-` and is not `default` or `openshift`. A user namespace SHALL be covered when it has at least one ResourceQuota or at least one LimitRange. Zero user namespaces SHALL be NOT_APPLICABLE. Any uncovered user namespace SHALL be FAIL. All user namespaces covered SHALL be PASS. Platform namespaces SHALL NOT FAIL this check. The project-request template SHALL NOT be scored. `7.6.rq` bars SHALL not change in this change.

#### Scenario: uncovered user namespace fails
- GIVEN a user namespace with no ResourceQuota and no LimitRange
- WHEN core evaluation runs
- THEN `7.6.quota.coverage` status is FAIL

#### Scenario: ResourceQuota covers the user namespace
- GIVEN a user namespace with at least one ResourceQuota
- AND no LimitRange in that namespace
- WHEN core evaluation runs
- THEN `7.6.quota.coverage` status is PASS

### Requirement: Sparse TSR alias for quota coverage
KB row `7.6.tsr.6_1_1_1_quota_resources_project_assignment` SHALL be a sparse alias (`content_from` exact `7.6.quota.coverage`, `include_in_findings = false`). It SHALL NOT target `7.6.rq`. Rows `7.6.tsr.6_1_1_quota_and_resources` and `7.6.tsr.6_1_1_2_cluster_quota_configuration` SHALL set `content_from` exact `7.6.quota.coverage`. There SHALL be no `content_from` chain through the TSR leaf.

#### Scenario: quota TSR aliases 7.6.quota.coverage
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_1_1_quota_resources_project_assignment` is loaded
- THEN `content_from` is `7.6.quota.coverage`
- AND `include_in_findings` is false

### Requirement: Native user-pod request scoring
Core evaluation SHALL emit `7.6.pod.requests` with title `Pod CPU and memory requests`. `_hc_error` on `pods_all` SHALL be SKIPPED. Missing payload, `_hc_not_found`, or zero items SHALL be NOT_APPLICABLE. Platform namespaces SHALL not be scored. Succeeded and Failed pods SHALL not be scored. Only `spec.containers` SHALL be inspected. Any user active pod missing CPU or memory requests SHALL be WARNING. Else PASS. The check SHALL NOT FAIL. `7.6.limitranges` and `7.6.req_limits` bars SHALL not change.

#### Scenario: missing CPU request is WARNING
- GIVEN a user-namespace Running pod whose container has memory requests and no CPU requests
- WHEN core evaluation runs
- THEN `7.6.pod.requests` status is WARNING
- AND the status is not FAIL

### Requirement: Sparse TSR alias for pod requests
KB row `7.6.tsr.6_1_2_requests_and_limits` SHALL be a sparse alias (`content_from` exact `7.6.pod.requests`, `include_in_findings = false`). It SHALL NOT target `7.6.limitranges` or `7.6.req_limits`.

#### Scenario: requests TSR aliases 7.6.pod.requests
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_2_requests_and_limits` is loaded
- THEN `content_from` is `7.6.pod.requests`
- AND `include_in_findings` is false

### Requirement: Collect NetworkPolicy lists
Live and supportshell collect SHALL write `networkpolicy` under `08_day2` via `oc get networkpolicy -A`.

#### Scenario: networkpolicy capture name exists
- GIVEN live `08_day2.sh`
- WHEN an operator inspects capture stems
- THEN `networkpolicy` is present as a capture name

### Requirement: Native orphan NetworkPolicy scoring
Core evaluation SHALL emit `7.6.netpol.orphan` with title `Orphan user NetworkPolicies`. Missing or `_hc_error` networkpolicy payload SHALL be SKIPPED. Missing or `_hc_error` `pods_all` payload SHALL be SKIPPED (do not FAIL labeled selectors against an empty pod list). Zero user-namespace policies SHALL be INFO. Empty `podSelector` SHALL NOT be an orphan. `matchExpressions` without `matchLabels` SHALL skip that policy. A labeled selector matching zero non-terminal pods in that namespace SHALL be FAIL. Else PASS. `7.6.prune.netpol` SHALL remain SKIPPED.

#### Scenario: labeled selector matching zero pods fails
- GIVEN a user NetworkPolicy with `matchLabels` that match zero non-terminal pods in that namespace
- WHEN core evaluation runs
- THEN `7.6.netpol.orphan` status is FAIL

#### Scenario: empty selector is not an orphan
- GIVEN user NetworkPolicies exist
- AND every user policy has an empty `podSelector` with no `matchLabels`
- WHEN core evaluation runs
- THEN `7.6.netpol.orphan` status is PASS

### Requirement: Sparse TSR alias for network policy pruning
KB row `7.6.tsr.6_1_5_3_network_policy_pruning` SHALL be a sparse alias (`content_from` exact `7.6.netpol.orphan`, `include_in_findings = false`). It SHALL NOT target `7.6.prune.netpol`.

#### Scenario: netpol TSR aliases 7.6.netpol.orphan
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_1_5_3_network_policy_pruning` is loaded
- THEN `content_from` is `7.6.netpol.orphan`
- AND `include_in_findings` is false

### Requirement: Native image registrySources scoring
Core evaluation SHALL emit `7.6.image.registry_sources` with title `Image registry sources`. `_hc_error` SHALL be SKIPPED. Missing or `_hc_not_found` SHALL be NOT_APPLICABLE. Allowed and blocked both non-empty SHALL be FAIL. Else insecure non-empty SHALL be WARNING. Else allowed empty and blocked empty SHALL be INFO. Else PASS. Empty connected-cluster defaults SHALL NOT FAIL. `7.6.image_mgmt` bars SHALL not change.

#### Scenario: empty allow and block is INFO
- GIVEN `registrySources` with empty allowed, blocked, and insecure lists
- WHEN core evaluation runs
- THEN `7.6.image.registry_sources` status is INFO

#### Scenario: allowed and blocked together fails
- GIVEN non-empty `allowedRegistries` and non-empty `blockedRegistries`
- WHEN core evaluation runs
- THEN `7.6.image.registry_sources` status is FAIL

### Requirement: Sparse TSR alias for images patch management
KB row `7.6.tsr.6_2_3_images_patch_management` SHALL be a sparse alias (`content_from` exact `7.6.image.registry_sources`, `include_in_findings = false`). It SHALL NOT target `7.6.image_mgmt`.

#### Scenario: image TSR aliases 7.6.image.registry_sources
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_2_3_images_patch_management` is loaded
- THEN `content_from` is `7.6.image.registry_sources`
- AND `include_in_findings` is false

### Requirement: Native Alertmanager receiver scoring
Core evaluation SHALL emit `7.6.alert_receivers` with title `Alert receivers`. The engine SHALL read `results["08_day2"]["alertmanager_receivers"]`. Collect SHALL persist `receiver_names` only and SHALL NOT persist decoded Alertmanager YAML or webhook URLs. Missing collect or `_hc_error` SHALL be SKIPPED. Names `null`, `Default`, `default`, `Watchdog`, and `watchdog` SHALL be ignored. Zero names remaining after that ignore list SHALL be FAIL. Else PASS. The engine SHALL NOT score AlertmanagerConfig custom resources.

#### Scenario: empty receiver_names is FAIL
- GIVEN redacted collect with `receiver_names` `[]`
- WHEN evaluate_checks core
- THEN `7.6.alert_receivers` is FAIL

#### Scenario: ignored-only names is FAIL
- GIVEN names `["null"]`
- WHEN evaluate_checks core
- THEN `7.6.alert_receivers` is FAIL

#### Scenario: a real receiver name is PASS
- GIVEN names `["pagerduty-prod"]`
- WHEN evaluate_checks core
- THEN `7.6.alert_receivers` is PASS

#### Scenario: collection error is SKIPPED
- GIVEN `_hc_error`
- WHEN evaluate_checks core
- THEN `7.6.alert_receivers` is SKIPPED

### Requirement: Sparse TSR alias for alert receivers
KB row `7.6.tsr.6_3_2_alert_receivers` SHALL be a sparse alias (`content_from` exact `7.6.alert_receivers`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: alert receivers TSR aliases native
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_3_2_alert_receivers` is loaded
- THEN `content_from` is `7.6.alert_receivers`

### Requirement: Native ClusterVersion failed or partial hops
Core evaluation SHALL emit `7.6.upgrade.failed_hops` with title `ClusterVersion failed or partial hops`. `_hc_error` SHALL be SKIPPED. Missing or `_hc_not_found` SHALL be NOT_APPLICABLE. Empty `status.history` SHALL be NOT_APPLICABLE. Any history item whose `state` is `Partial` or `Failed` (case-sensitive) SHALL be FAIL. Else when history is present the status SHALL be PASS. The check SHALL never emit WARNING. `7.6.upgrade.history` Completed-only bars SHALL not change in this change.

#### Scenario: Partial hop fails
- GIVEN ClusterVersion history containing a hop with `state` `Partial`
- WHEN core evaluation runs
- THEN `7.6.upgrade.failed_hops` status is FAIL
- AND the status is not PASS

#### Scenario: all Completed hops pass
- GIVEN ClusterVersion history whose hops are all `Completed`
- WHEN core evaluation runs
- THEN `7.6.upgrade.failed_hops` status is PASS
- AND the status is not FAIL

#### Scenario: collection error is skipped
- GIVEN clusterversion payload with `_hc_error`
- WHEN core evaluation runs
- THEN `7.6.upgrade.failed_hops` status is SKIPPED
- AND the status is not FAIL

### Requirement: Update-history TSR stays on Completed native
KB row `7.6.tsr.6_2_1_update_history` SHALL remain a sparse alias (`content_from` exact `7.6.upgrade.history`). It SHALL NOT use `content_from` `7.6.upgrade.failed_hops`.

#### Scenario: update history TSR is not retargeted
- GIVEN production `load_kb()`
- WHEN entry `7.6.tsr.6_2_1_update_history` is loaded
- THEN `content_from` is `7.6.upgrade.history`
- AND `content_from` is not `7.6.upgrade.failed_hops`

### Requirement: Wrong-story TSR rows stay canonical
This requirement is withdrawn. The four former wrong-story TSR leaves SHALL sparse-alias the natives in this spec.

#### Scenario: quota leaf is not an alias
This scenario is withdrawn. Quota, requests, netpol, and image TSR leaves SHALL alias their natives.

### Requirement: Active-alerts hop is out of this change
KB row `7.6.tsr.6_3_1_active_alerts` SHALL NOT be retargeted by this change.

#### Scenario: active-alerts hop unchanged here
- GIVEN this change
- WHEN KB is loaded
- THEN `7.6.tsr.6_3_1_active_alerts` is not required to point at `7.5.node.utilization`

### Requirement: Kubelet Ready and upgrade Partial stay non-FAIL
`7.5.kubelet_health` SHALL remain WARNING when any node Ready is not True. `7.6.upgrade.history` SHALL NOT FAIL Partial or Failed hops in this change.

#### Scenario: kubelet not Ready is WARNING
- GIVEN a node whose Ready condition is not True
- WHEN core evaluation runs
- THEN `7.5.kubelet_health` status is WARNING

### Requirement: Native cluster platform-operator rollup
Core evaluation SHALL emit `7.3.co.platform` after per-operator `7.3.co.{name}` rows when clusteroperators parse to a non-empty per-operator list. Status SHALL be FAIL if any per-operator row is FAIL; else WARNING if any per-operator row is WARNING; else PASS. Per-operator check_ids SHALL remain, including exact `7.3.co.kube-apiserver`. Missing clusteroperators SHALL emit NOT_APPLICABLE on `7.3.co.platform` and SHALL keep existing `7.3.co` NOT_APPLICABLE. The rollup SHALL NOT re-read operator conditions or call `find_degraded_operators`. Per-operator FAIL/WARNING/PASS bars SHALL not change in this change.

#### Scenario: any degraded operator rolls up to FAIL
- GIVEN at least one per-operator row with status FAIL
- WHEN core evaluation runs
- THEN `7.3.co.platform` status is FAIL
- AND per-operator check_ids are still emitted

#### Scenario: all per-operator rows PASS
- GIVEN every per-operator row is PASS
- WHEN core evaluation runs
- THEN `7.3.co.platform` status is PASS

#### Scenario: missing clusteroperators is NOT_APPLICABLE on both ids
- GIVEN clusteroperators payload is missing or empty
- WHEN core evaluation runs
- THEN `7.3.co.platform` status is NOT_APPLICABLE
- AND `7.3.co` status is NOT_APPLICABLE

### Requirement: Sparse TSR aliases for platform operators
KB rows `7.3.tsr.3_2_1_platform_operators` and `7.3.tsr.3_2_operators` SHALL be sparse aliases (`content_from` exact `7.3.co.platform`, `include_in_findings = false`). KB rows `7.3.tsr.3_2_2_additional_operators` and `7.7.ccx_internal.uninstalled_operators_with_leftover_resources` SHALL be sparse aliases (`content_from` exact `7.3.co.platform`, `include_in_findings = false`). There SHALL NOT be a `content_from` chain through `7.3.tsr.3_2_1_platform_operators`. Alias rows SHALL NOT overlay inherited narrative keys.

#### Scenario: 3.2.1 and 3.2 parent alias the rollup
- GIVEN production `load_kb()`
- WHEN entries `7.3.tsr.3_2_1_platform_operators` and `7.3.tsr.3_2_operators` are loaded
- THEN each `content_from` is `7.3.co.platform`
- AND each `include_in_findings` is false

#### Scenario: additional-operators and leftover CCX alias the rollup
- GIVEN production `load_kb()`
- WHEN entries `7.3.tsr.3_2_2_additional_operators` and `7.7.ccx_internal.uninstalled_operators_with_leftover_resources` are loaded
- THEN each `content_from` is `7.3.co.platform`
- AND each `include_in_findings` is false

### Requirement: CRD TSR aliases CRD count not operators
KB row `7.3.tsr.3_3_custom_resource_definitions` SHALL be a sparse alias (`content_from` exact `7.3.crds`, `include_in_findings = false`). It SHALL NOT target `7.3.co.platform` or `7.3.tsr.3_2_1_platform_operators`. CRD WARNING when count is greater than 500 SHALL not change in this change.

#### Scenario: CRD TSR aliases 7.3.crds
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_3_custom_resource_definitions` is loaded
- THEN `content_from` is `7.3.crds`
- AND `include_in_findings` is false

### Requirement: Sparse TSR alias for ingress sharding
KB row `7.3.tsr.3_8_3_ingress_sharding` SHALL be a sparse alias (`content_from` exact `7.3.ingress.sharding`, `include_in_findings = false`). Ingress sharding bars SHALL not change in this change.

#### Scenario: sharding TSR aliases the native
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_8_3_ingress_sharding` is loaded
- THEN `content_from` is `7.3.ingress.sharding`
- AND `include_in_findings` is false

### Requirement: Sparse TSR aliases for machine config pool
KB rows `7.3.tsr.3_15_machine_config_pool` and `7.5.tsr.5_2_machine_config` SHALL be sparse aliases (`content_from` exact `7.3.misc.mcp`, `include_in_findings = false`). There SHALL NOT be a `content_from` chain through `7.3.tsr.3_15_machine_config_pool`. MCP WARNING on degraded or updating SHALL not change in this change. These rows SHALL NOT alias `7.5.mcp_health`.

#### Scenario: MCP TSR and 5.2 alias 7.3.misc.mcp
- GIVEN production `load_kb()`
- WHEN entries `7.3.tsr.3_15_machine_config_pool` and `7.5.tsr.5_2_machine_config` are loaded
- THEN each `content_from` is `7.3.misc.mcp`
- AND each `include_in_findings` is false

### Requirement: Native CSI CSO allow-list scoring
Core evaluation SHALL emit `7.3.storage.csi_cso` with title `CSI driver CSO allow-list`. `_hc_error` on CSIDriver or CRDs SHALL be SKIPPED. Missing CSIDriver list SHALL be NOT_APPLICABLE. Zero CSIDriver items SHALL be WARNING. CSO enum SHALL be extracted from CRD `clustercsidrivers.operator.openshift.io` by walking dict and list nodes and collecting `enum` lists that contain `ebs.csi.aws.com`. Empty enum SHALL be SKIPPED. A CSIDriver name SHALL be allowed when it is in that enum, starts with `openshift-storage.`, or equals `lvm.csi.topolvm.io`, `topolvm.io`, or `kubevirt.io.hostpath-provisioner`. Any other name SHALL be third-party. Any third-party SHALL be WARNING. All allowed SHALL be PASS. Third-party SHALL NOT be FAIL. `7.3.storage.csi` inventory bars SHALL not change in this change.

#### Scenario: nfs outside enum is WARNING
- GIVEN CSIDriver items include `nfs.csi.k8s.io`
- AND the ClusterCSIDriver enum includes `ebs.csi.aws.com` and does not include `nfs.csi.k8s.io`
- WHEN core evaluation runs
- THEN `7.3.storage.csi_cso` status is WARNING
- AND the status is not FAIL

#### Scenario: all names in enum is PASS
- GIVEN every CSIDriver name is in the ClusterCSIDriver enum
- WHEN core evaluation runs
- THEN `7.3.storage.csi_cso` status is PASS

#### Scenario: empty enum is SKIPPED
- GIVEN CSIDriver items are present
- AND no enum list containing `ebs.csi.aws.com` is found
- WHEN core evaluation runs
- THEN `7.3.storage.csi_cso` status is SKIPPED

#### Scenario: inventory CSI stays independent
- GIVEN a scored CSIDriver payload
- WHEN core evaluation runs
- THEN `7.3.storage.csi` is still emitted
- AND `7.3.storage.csi_cso` does not replace its scoring

### Requirement: Sparse TSR alias for CSI drivers
KB row `7.3.tsr.3_9_5_csi_drivers` SHALL be a sparse alias (`content_from` exact `7.3.storage.csi_cso`, `include_in_findings = false`). It SHALL NOT target `7.3.storage.csi`. Alias rows SHALL NOT overlay inherited narrative keys. Platform-operator TSR SHALL NOT alias `7.5.operator_state`.

#### Scenario: CSI TSR aliases 7.3.storage.csi_cso
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_9_5_csi_drivers` is loaded
- THEN `content_from` is `7.3.storage.csi_cso`
- AND `include_in_findings` is false

### Requirement: Exact kube-apiserver KB remains
Exact KB row `7.3.co.kube-apiserver` SHALL remain. Exact `7.3.co.platform` SHALL win over glob `7.3.co.*`.

#### Scenario: kube-apiserver exact row still exists
- GIVEN production `load_kb()`
- WHEN entry `7.3.co.kube-apiserver` is loaded
- THEN the row is present as an exact check_id

### Requirement: Sparse TSR aliases for master memory, authentication, AZ labels, and HAProxy HA
KB row `7.1.tsr.1_4_1_3_master_memory` SHALL be a sparse alias (`content_from` exact `7.1.nodes.master_mem`, `include_in_findings = false`). KB row `7.1.tsr.1_5_17_authentication` SHALL be a sparse alias (`content_from` exact `7.1.sys.auth`, `include_in_findings = false`). KB row `7.2.tsr.2_2_2_master_av_zone_labels` SHALL be a sparse alias (`content_from` exact `7.2.topo.master_az`, `include_in_findings = false`). KB row `7.2.tsr.2_2_3_haproxy_ha` SHALL be a sparse alias (`content_from` exact `7.2.topo.haproxy_ha`, `include_in_findings = false`). Alias rows SHALL NOT overlay inherited narrative keys. Master memory FAIL when any master capacity is less than 16 GiB SHALL not change in this change. Authentication WARNING when no IdP or all HTPasswd SHALL not change. AZ WARNING when fewer than 3 zones SHALL not change. HAProxy WARNING when replicas or availableReplicas are less than 2 SHALL not change.

#### Scenario: master-memory TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.1.tsr.1_4_1_3_master_memory` is loaded
- THEN `content_from` is `7.1.nodes.master_mem`
- AND `include_in_findings` is false

#### Scenario: authentication TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.1.tsr.1_5_17_authentication` is loaded
- THEN `content_from` is `7.1.sys.auth`
- AND `include_in_findings` is false

#### Scenario: AZ TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.2.tsr.2_2_2_master_av_zone_labels` is loaded
- THEN `content_from` is `7.2.topo.master_az`
- AND `include_in_findings` is false

#### Scenario: HAProxy TSR is a sparse alias
- GIVEN production `load_kb()`
- WHEN entry `7.2.tsr.2_2_3_haproxy_ha` is loaded
- THEN `content_from` is `7.2.topo.haproxy_ha`
- AND `include_in_findings` is false

### Requirement: Native CoreDNS firing alerts
Core evaluation SHALL emit `7.1.dns.coredns_alerts` from `07_cluster_health` `firing_alerts`. Status SHALL be FAIL if any parsed alert has `state` equal to firing (case-insensitive) and `labels.alertname` exactly one of `CoreDNSErrorsHigh`, `CoreDNSHealthCheckSlow`, or `CoreDNSPanicking`. Pending alerts SHALL not FAIL. Missing or `_is_missing` `firing_alerts` SHALL emit SKIPPED. Else PASS. Non-CoreDNS alert names SHALL not FAIL this check.

#### Scenario: CoreDNSErrorsHigh firing is FAIL
- GIVEN a firing alert whose `alertname` is `CoreDNSErrorsHigh`
- WHEN core evaluation runs
- THEN `7.1.dns.coredns_alerts` status is FAIL

#### Scenario: no CoreDNS firing alerts is PASS
- GIVEN a parsed alert list with no matching CoreDNS names in firing state
- WHEN core evaluation runs
- THEN `7.1.dns.coredns_alerts` status is PASS

#### Scenario: missing firing_alerts is SKIPPED
- GIVEN `firing_alerts` is missing or `_is_missing`
- WHEN core evaluation runs
- THEN `7.1.dns.coredns_alerts` status is SKIPPED

### Requirement: Sparse aliases for DNS TSR and CoreDNS CCX
KB rows `7.1.tsr.1_5_2_3_dns_alerts` and `7.7.ccx_internal.high_core_dns_errors_high_alerts` SHALL be sparse aliases (`content_from` exact `7.1.dns.coredns_alerts`, `include_in_findings = false`). There SHALL NOT be a `content_from` chain through `7.1.tsr.1_5_2_3_dns_alerts`.

#### Scenario: DNS TSR and CoreDNS CCX alias the native
- GIVEN production `load_kb()`
- WHEN entries `7.1.tsr.1_5_2_3_dns_alerts` and `7.7.ccx_internal.high_core_dns_errors_high_alerts` are loaded
- THEN each `content_from` is `7.1.dns.coredns_alerts`
- AND each `include_in_findings` is false

### Requirement: Non-CoreDNS former hops park on critical alerts
KB rows `7.7.ccx_internal.high_severity_alerts`, `7.3.tsr.3_5_9_etcd_alerts`, `7.5.tsr.5_11_health_related_alerts`, `7.5.tsr.5_11_2_node_alerts`, `7.5.tsr.5_11_3_overcommit_alerts`, and `7.6.tsr.6_3_1_active_alerts` SHALL be sparse aliases (`content_from` exact `7.5.alerts.critical`, `include_in_findings = false`). Those rows SHALL NOT target `7.1.dns.coredns_alerts`.

#### Scenario: etcd alerts hop is not CoreDNS
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_5_9_etcd_alerts` is loaded
- THEN `content_from` is `7.5.alerts.critical`
- AND `include_in_findings` is false

### Requirement: Native overlay-port posture
Core evaluation SHALL emit `7.1.net.overlay_ports` from `05_components` `network`. Status SHALL be SKIPPED when the payload has `_hc_error`. Status SHALL be NOT_APPLICABLE when the payload is missing or `_hc_not_found`. Status SHALL be PASS when `spec.networkType` is `OVNKubernetes`. PASS evidence SHALL name 6081/udp (all nodes), 6443/tcp (control-plane), 2379/tcp and 2380/tcp (control-plane), 10250/tcp (all nodes), and SHALL include the phrase `ports not probed`. Status SHALL be WARNING when `spec.networkType` is `OpenShiftSDN`. Status SHALL be INFO when `spec.networkType` is any other non-empty value. When `spec.networkType` is empty or missing, evaluation MAY apply a fallback of `OVNKubernetes` or `OpenShiftSDN` from ClusterOperator plugin detection and score PASS or WARNING as above; otherwise INFO. Status SHALL NEVER be FAIL. Collect SHALL NOT probe host iptables or cloud security groups for this check.

#### Scenario: OVNKubernetes is PASS
- GIVEN `network` with `spec.networkType` equal to `OVNKubernetes`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is PASS
- AND evidence contains `ports not probed`

#### Scenario: OpenShiftSDN is WARNING
- GIVEN `network` with `spec.networkType` equal to `OpenShiftSDN`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is WARNING

#### Scenario: collect error is SKIPPED
- GIVEN `network` with `_hc_error` set
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is SKIPPED

#### Scenario: missing network is NOT_APPLICABLE
- GIVEN `network` missing or `_hc_not_found`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is NOT_APPLICABLE

#### Scenario: other CNI is INFO
- GIVEN `network` with a non-empty `spec.networkType` that is neither `OVNKubernetes` nor `OpenShiftSDN`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is INFO

#### Scenario: empty networkType is INFO
- GIVEN `network` with `spec.networkType` empty or missing
- AND no ClusterOperator plugin fallback of `OVNKubernetes` or `OpenShiftSDN`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is INFO

### Requirement: Firewalls TSR sparse-aliases overlay ports
KB row `7.1.tsr.1_5_5_firewalls` SHALL be a sparse alias (`content_from` exact `7.1.net.overlay_ports`, `include_in_findings = false`). The alias SHALL NOT set `content_from` to `7.1.sys.firewall`. Alias rows SHALL NOT overlay inherited narrative keys. `7.1.sys.firewall` proxy-present WARNING SHALL not change.

#### Scenario: firewalls TSR aliases overlay ports
- GIVEN production `load_kb()`
- WHEN entry `7.1.tsr.1_5_5_firewalls` is loaded
- THEN `content_from` is `7.1.net.overlay_ports`
- AND `include_in_findings` is false
- AND `content_from` is not `7.1.sys.firewall`

### Requirement: Overlay ports are not probed
Evaluation SHALL NOT FAIL `7.1.net.overlay_ports` because ports were not probed. Host debug, iptables scrape, and security-group inventory SHALL stay out of this check.

#### Scenario: no FAIL for unprobed ports
- GIVEN `network` with `spec.networkType` equal to `OVNKubernetes`
- WHEN core evaluation runs
- THEN `7.1.net.overlay_ports` status is not FAIL

### Requirement: Native KB voice pass (stubs)
KB rows frozen in `tmp/hc_kb_live_parity_narratives/STUBS.txt` (non-comment lines) SHALL be native (`content_from` empty) and SHALL have `description` strip length at least 40 characters. Evaluators and scoring fields SHALL NOT change. Alias rows SHALL NOT gain inherited narrative keys in a voice pass. If the freeze list is empty, no TOML voice edits are required and `load_kb()` SHALL still succeed.

#### Scenario: Frozen native is no longer stub-length
- GIVEN production `load_kb()`
- AND a `check_id` listed in `STUBS.txt` (ignoring `#` lines)
- WHEN that entry is loaded
- THEN `content_from` is empty
- AND `len(description.strip())` is at least 40

#### Scenario: Empty freeze list needs no voice edits
- GIVEN `STUBS.txt` with no non-comment `check_id` lines
- WHEN this change is applied
- THEN no native scoring fields change
- AND `load_kb()` still succeeds

#### Scenario: Frozen natives do not overlay their aliases
- GIVEN a native `check_id` listed in `STUBS.txt` (non-comment lines)
- AND an alias row whose `content_from` equals that `check_id`
- WHEN the KB TOML files are read
- THEN the alias row does not set `description`, `recommendation`, or `verification`

#### Scenario: Empty freeze list leaves aliases unchanged
- GIVEN `STUBS.txt` with no non-comment `check_id` lines
- WHEN this change is applied
- THEN `load_kb()` succeeds
- AND no alias row gained inherited narrative keys from this change

### Requirement: Native OLM failed CSV scoring
Core evaluation SHALL emit `7.3.olm.failed_csv` with title `OLM failed ClusterServiceVersions`. `_hc_error` SHALL be SKIPPED. Missing payload SHALL be NOT_APPLICABLE. Zero ClusterServiceVersion items SHALL be NOT_APPLICABLE. Any item with `status.phase` equal to `Failed` SHALL be FAIL. Else any item whose phase is neither `Succeeded` nor empty SHALL be WARNING. Else PASS. Succeeded copied CSVs SHALL NOT FAIL or WARNING. `7.3.co.platform` scoring SHALL not change in this change.

#### Scenario: Failed CSV is FAIL
- GIVEN a ClusterServiceVersion with `status.phase` `Failed`
- WHEN core evaluation runs
- THEN `7.3.olm.failed_csv` status is FAIL

#### Scenario: Succeeded CSV is PASS
- GIVEN only ClusterServiceVersions with `status.phase` `Succeeded`
- WHEN core evaluation runs
- THEN `7.3.olm.failed_csv` status is PASS
- AND the status is not FAIL

#### Scenario: Replacing CSV is WARNING
- GIVEN a ClusterServiceVersion with `status.phase` `Replacing`
- AND no Failed phase
- WHEN core evaluation runs
- THEN `7.3.olm.failed_csv` status is WARNING

### Requirement: Additional operators TSR stays on platform rollup
KB row `7.3.tsr.3_2_2_additional_operators` SHALL keep `content_from` exact `7.3.co.platform`. This change SHALL NOT retarget that row onto `7.3.olm.failed_csv`. Insights `7.7.ccx_internal.uninstalled_operators_with_leftover_resources` SHALL NOT receive `content_from` from this native.

#### Scenario: additional operators TSR remains on co.platform
- GIVEN production `load_kb()`
- WHEN entry `7.3.tsr.3_2_2_additional_operators` is loaded
- THEN `content_from` is `7.3.co.platform`

### Requirement: Chapter 7 omits content_from aliases
Chapter 7 check-result tables and category stats SHALL omit a check when its KB entry has a non-empty `content_from`. A check with no KB entry or with empty `content_from` SHALL appear. CCX checks without `content_from` SHALL appear. `include_in_findings` SHALL continue to govern Chapter 6 only.

#### Scenario: Alias row omitted from Chapter 7
- GIVEN a `CheckResult` whose KB entry has non-empty `content_from`
- WHEN `_build_check_results_table` renders that category
- THEN the alias KB title is absent from the table

#### Scenario: Native row kept in Chapter 7
- GIVEN a `CheckResult` whose KB entry has empty `content_from`
- WHEN `_build_check_results_table` renders that category
- THEN the native KB title is present in the table

#### Scenario: Chapter 6 findings ignore the Chapter 7 filter
- GIVEN a native FAIL check that is eligible for findings
- WHEN `derive_findings` runs
- THEN a finding for that native `check_id` is present

