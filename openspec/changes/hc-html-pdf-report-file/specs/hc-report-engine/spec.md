# Health Check Report Engine (`hc-html-pdf-report-file` delta)

## ADDED Requirements

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
