# Health Check Report Engine (`hc-omit-findings` delta)

## MODIFIED Requirements

### Requirement: Report CLI and artifacts
`hc_report.cli` SHALL load results, evaluate checks, derive findings, and write markdown plus audit JSON under the output directory.

#### Scenario: Public flags stay stable
- GIVEN `parse_args()`
- WHEN the CLI is invoked
- THEN it accepts `--results-dir`, `--output-dir`, `--config`, `--template`, `--exec-summary`, `--check-profile` (`core` | `extended` | `advisory`), `--ccx-baseline-status`, `--catalog-path`, `--tsr-html`, `--dry-run`, `--omit-check-ids`, and `--omit-strict`
- AND those existing flag names are not renamed

## ADDED Requirements

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
