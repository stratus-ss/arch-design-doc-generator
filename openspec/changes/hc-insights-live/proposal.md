# Change Proposal: hc-insights-live

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_insights_live_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

`evaluate_ccx` SHALL emit `NOT_APPLICABLE` for every `CCX_STATIC_CHECK_IDS` row when InsightsOperator reporting is disabled. When reporting is enabled (or InsightsOperator is missing) and `12_ccx/ccx_rules` is `_hc_not_found` or absent, those rows SHALL be `SKIPPED` with evidence naming `HC_CCX_RULES_FILE` and Insights Available. Matched payload rows SHALL keep the existing `_status` mapping. Unmatched CVE ids SHALL stay `SKIPPED`. Missing rules file SHALL never FAIL. This change SHALL NOT scrape cloud Insights/Advisor HTTP APIs and SHALL NOT invent CVE FAIL.

Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_insights_live_2026-08-29.md`
