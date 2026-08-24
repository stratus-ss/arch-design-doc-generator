`generate_report.py` is a thin wrapper over the `hc_report/` Python package:

```
scripts/health_check/hc_report/
  models.py        — CheckResult, Finding dataclasses (Finding carries impact/impact_scope/impact_detail)
  loader.py        — load_results() (manifest or directory scan)
  metadata.py      — derive_metadata() from collected JSON
  registry.py      — check-profile dispatch (core/extended/advisory)
  evaluators/      — per-category check functions (12 modules plus `_common.py` and `_shared_checks.py`)
  parity.py        — TSR/CCX additive parity expansion
  tsr_parser.py    — parse TSR HTML exports into parity status inputs
  catalogs/        — tsr_ccx_crosswalk.json (+ README)
  kb/               — external TOML knowledge base: descriptions, recommendations,
                       optional verification, impact metadata, and version-aware doc
                       links, keyed by check_id. Sparse `content_from` rows are aliases
                       (they inherit verification); see root README Knowledge Base.
  kb_loader.py      — loads/version-resolves the KB (including `content_from` aliases);
                       get_recommendation() joins optional verification with a bold
                       **Verification:** line; get_links()/get_impact()
  link_review/      — suggest + HTTP-check KB documentation URLs (does not rewrite TOMLs)
  build_crosswalk_catalog.py — regenerates catalogs/tsr_ccx_crosswalk.json
  findings.py      — derive_findings(); resolves recommendation/impact via kb_loader.py,
                       falling back to notes.py, then a generic [NEEDS REVIEW] placeholder
  renderer.py      — render_report() template slot substitution; emits a conditional
                       "Level of Impact" block per finding when KB impact data is present
  notes.py         — KB-first per-check documentation links; small _CHECK_NOTES fallback table
  cli.py           — argument parsing, orchestration
```

Code quality is enforced via `ruff.toml` (C901 ≤ 15, max-branches ≤ 15, max-statements ≤ 50).
