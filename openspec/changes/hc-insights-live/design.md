# Design: Insights CCX CVE ingest without a rules file

Retune `evaluate_ccx` only. Read InsightsOperator from `results["03_base_platform"]["insightsoperator"]` and reuse `_insights_reporting_disabled` from `platform.py`. Keep `CCX_STATIC_CHECK_IDS` unchanged. Keep payload matching in `_collect_runtime_ccx`.

Do not add collect scripts. Do not call Advisor HTTP. Do not rewrite CVE matching. Leftover-OLM Insights CRDs stay out of this change.

Scoring matrix is in the delta spec.
