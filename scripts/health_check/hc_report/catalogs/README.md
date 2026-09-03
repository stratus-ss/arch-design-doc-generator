# TSR/CCX Catalogs

This directory stores the additive parity catalog used by the health-check report pipeline.

- `tsr_ccx_crosswalk.json` — normalized TSR section checks and CCX rules mapped to internal check IDs and categories.

## Regeneration

Rebuild the catalog from a TSR HTML export:

```bash
make hc-build-catalog TSR_HTML=/path/to/tsr.html
```

Or call the script directly:

```bash
python3 scripts/health_check/hc_report/build_crosswalk_catalog.py \
  --input-html "/path/to/tsr.html" \
  --output-json "scripts/health_check/hc_report/catalogs/tsr_ccx_crosswalk.json"
```

## Notes

- Catalog entries are additive metadata and do not remove/rename existing deterministic checks.
- TSR section entries are **leaf checks only**. Tree-view group/dropdown headers (nodes with a child list, e.g. "1.5. Other Basic Checks") are skipped by `build_crosswalk_catalog.py`.
- TSR entries default to `SKIPPED` unless a matching TSR HTML export supplies a real status.
- CCX entries use live `12_ccx/ccx_rules.json` or CCX records parsed from TSR HTML. Without that data they stay SKIPPED unless `--ccx-baseline-status` is enabled.
- Report profiles (`health_check.check_profile` in `project.yaml`: `core`, `extended`, `advisory`) control whether parity/CCX expansion runs. Default is `advisory`.
- Optional runtime TSR HTML: pass `--tsr-html` / `HC_TSR_HTML` / `health_check.tsr_html_path`, or drop files under `output/tsr_html/` (`HC_TSR_HTML_DIR`) so `tsr_parser.py` can replace placeholder statuses.
