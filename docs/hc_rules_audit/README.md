# Health-check native scoring rules (audit)

Audience: a consultant or reviewer who should not need to open Python.

These documents describe **what the native evaluators actually score** when a report is generated from collected cluster JSON. They are an audit of the engine, not a rewrite of it.

| File | Contents |
|------|----------|
| [01_evaluator_rules.md](01_evaluator_rules.md) | Every native `check_id` pattern and the condition → status matrix |
| [02_rules_vs_openshift_docs.md](02_rules_vs_openshift_docs.md) | Same rules vs on-disk OpenShift 4.22 documentation |
| [03_where_to_encode_rules.md](03_where_to_encode_rules.md) | Whether scoring should stay in Python (hybrid recommendation) |

## Source of truth

Scoring is implemented in `scripts/health_check/hc_report/evaluators/`. Status is assigned in Python (`PASS`, `FAIL`, `WARNING`, `INFO`, `SKIPPED`, `NOT_APPLICABLE`).

The TOML knowledge base (`scripts/health_check/hc_report/kb/`) supplies report **prose** (title, recommendation, verification commands). The engine does **not** execute those `oc` / `awk` snippets. If verification text and Python disagree, this catalog follows Python.

TSR HTML / CCX catalog rows are **out of scope** here. Without a TSR they stay `SKIPPED` in the parity expander; they are not native evaluator rules.

## Related runbook

[HC_CHECK_RATIONALE.md](../HC_CHECK_RATIONALE.md) is a consultant validation companion (jq paths, live `oc`, intended rationale). It can lag the code. If that runbook and this catalog disagree, **this catalog follows the evaluators**.

## How to read Doc 01

Each row is one `check_id` or a **pattern** (for example `7.3.co.{name}` for one check per cluster operator). Dynamic names are not listed individually.

Missing collect data usually becomes `NOT_APPLICABLE` via `_not_applicable()` (`evidence` defaults to “Data not collected”) unless a function uses `SKIPPED` or omits the check entirely. Those exceptions are called out in the matrix.
