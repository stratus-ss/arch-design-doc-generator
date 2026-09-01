`generate_report.py` is a thin wrapper over the `hc_report/` Python package:

```
scripts/health_check/hc_report/
  models.py        — CheckResult, Finding dataclasses (Finding carries impact/impact_scope/impact_detail)
  loader.py        — load_results() (manifest or directory scan)
  metadata.py      — derive_metadata() from collected JSON
  registry.py      — native category evaluators 03–11 (`get_core_registry`)
  evaluators/      — `evaluate_checks()` runs the registry then `parity.py` for `extended`/`advisory`
                     (`platform`, `topology`, `components` plus infra/network/misc helpers,
                     `layered`, `health`, `day2`, `security`, `metrics`, `hardware`)
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
  findings.py      — derive_findings() / derive_findings_with_tsr(); recommendation/impact via kb_loader.py
  omit_findings.py — optional Chapter 6 filter → `{stem}_pruned.md`
  renderer.py      — render_report() template slot substitution; emits a conditional
                       "Level of Impact" block per finding when KB impact data is present
  notes.py         — `get_note()` fallback links used by the renderer when KB links are empty
  cli.py           — argument parsing, orchestration (`cli.main`)
```

Code quality is enforced via `ruff.toml` (C901 ≤ 15, max-branches ≤ 15, max-statements ≤ 50).
