# Design: family-level native scoring from Plan 2a JSON

Wire existing check IDs where they already exist. Mint only `7.3.storage.localvolume`, `7.4.odf.state`, and `7.4.rhoso.state`. Do not emit one ID per COLLECT_GAP leaf.

Optional product CRs: `_hc_not_found` or empty items → NOT_APPLICABLE (not FAIL). FeatureGate missing capture stays SKIPPED. PDB empty list is INFO.

CCX: `evaluators/ccx.py` emits four catalog CVE/external IDs on core. Score from `12_ccx/ccx_rules.json` when a title/id matches; otherwise SKIPPED. Do not register a 12th category. Do not emit the 21 CCX internals that duplicate natives. Do not emit 142 html-unmapped rows.

KB stubs only (`7_7_ccx.toml` plus rows for new family IDs). Scoring matrices live in `docs/HC_CHECK_RATIONALE.md`.
