# Where should native scoring rules live?

This note is analysis only. It does not migrate the engine. It answers whether FAIL/WARNING/INFO should stay in Python and what a more editable layout would look like.

## Current encoding

Native scoring is Python: `scripts/health_check/hc_report/evaluators/` assigns `CheckResult.status` from collected JSON. Shared floors (4 / 2 / 16.0 / 8.0 / 100.0) and Automatic-approval WARNING live in `_common.py`. Chapter files contain both **control flow** (operator `Degraded == True`) and **numbers** (WAL p99 &gt; 10 ms).

The TOML knowledge base (`hc_report/kb/7_*.toml`, loaded by `kb_loader.py`) is **narrative after the fact**: title, recommendation, `verification` (human `oc` / awk), impact, `finding_on_info`, `include_in_findings`, `priority_hint`. The engine does **not** execute `verification`. If awk text and Python disagree, Python wins. `finding_on_info` only affects Chapter 6 findings, not Chapter 7 status.

TSR/CCX catalog rows in `catalogs/tsr_ccx_crosswalk.json` are a third store: without HTML they are SKIPPED. They are not this native-rule problem.

`docs/HC_CHECK_RATIONALE.md` is a consultant runbook. It can lag the code. It is not a scorer.

## Who needs to edit what

An engagement lead changing a sentence should edit KB TOML. An engineer changing “what is a FAIL” today must find an `if` in an evaluator, and an outsider cannot see that without opening Python—the reason this audit exists.

Doc 02’s rollup matters: many rows are **docs-silent** or **engineering-judgment**. Moving numbers into TOML does not invent a Red Hat SLA. It only makes the **engine’s** bar reviewable and greppable. The 7.1 versus 7.2 split on the same install table (WARNING versus FAIL) is exactly the kind of mapping that should be a named field, not two copy-pasted `if` blocks that later diverge again.

## Options

### A. Keep all scoring in Python

**Pros:** One language; branching stays real code; tests already target functions; no load-time schema.  
**Cons:** Outsiders cannot audit without a catalog (this folder) that will drift; changing 500 ms vs 1000 ms is a code review; 7.1 vs 7.2 already disagree on WARNING vs FAIL for the same install table.

### B. Numeric thresholds and enum mappings on existing KB rows

Add keys such as `warn_ms`, `fail_ms`, `warn_percent` on `[[checks]]`. Evaluators look up `check_id` and compare.

**Pros:** One file per chapter already exists; consultants already edit TOML.  
**Cons:** KB is easy to confuse with `verification=` (documentation, not scoring). `content_from` aliases would inherit cutoffs whether or not that is wanted. Full if/else trees still cannot live here without becoming a DSL.

### C. Separate `rules.yaml` / `rules.toml` keyed by `check_id`

Evaluators become thin interpreters.

**Pros:** Clear “this file is the scorer.”  
**Cons:** A second store next to KB and Python; YAML that encodes Degraded/Progressing/Available becomes a programming language with worse tests.

### D. Hybrid: qualitative Kubernetes conditions stay in Python; numeric cutoffs move to data

**Pros:** Matches how the code already splits: CO Degraded is not a number; WAL 10/50 ms is. Outsiders edit cutoffs; engineers keep condition graphs. Matches Doc 02: conflicts and mixed rows are often **status mapping**, not a missing Red Hat table.  
**Cons:** Two places to look (Python for shape, data for numbers). Load must **fail** if a required cutoff key is missing (no silent in-code default in production). Existing pytest that hard-codes 500/1000 would need to read the same TOML so tests cannot drift from the file consultants edit.

## Recommendation

Choose **D (hybrid)**.

OpenShift condition checks (`Degraded=True` → FAIL) are control flow. Putting them in YAML tends to become a second programming language. Cutoffs (500 ms, 90%, 16 GiB, 10 ms WAL) are what outsiders want to audit and what drifts versus 4.22 txt. The KB is the wrong place to **hide** scoring if `verification=` remains documentation-only. Option B is acceptable **only** for numeric/enum fields on the canonical `check_id`, not for full branching—and only if the keys are named so nobody thinks awk is the engine.

Keep option A until a dedicated cutoff schema exists. Do not adopt a rules DSL or OPA/Rego. Do not store scoring only in `HC_CHECK_RATIONALE.md`.

## Sketch of hybrid

Numeric example:

```toml
[[checks]]
check_id = "7.8.apiserver.latency"
warn_ms = 500
fail_ms = 1000
```

`metrics.py` reads those fields, compares the Prometheus P99, and still builds evidence strings in Python. Missing `warn_ms`/`fail_ms` at `load_kb()` → hard error.

Qualitative example stays in Python: cluster operator `Degraded` True → FAIL, else Available ≠ True → WARNING (`components._evaluate_cluster_operators`). No TOML for that graph.

Shared install floors could be one `[thresholds.install]` table (4, 2, 16, 8, 100) referenced by both 7.1 and 7.2, with **separate** keys for status (`7.1_master_cpu_status = "WARNING"` vs `7.2_node_cpu_status = "FAIL"`) so the 7.1/7.2 split is explicit instead of accidental.

## What this audit does not do

No migration, no schema, no dual-write, no evaluator refactor. Doc 01 is the outsider catalog until a cutoff file exists. Doc 02 is the 4.22 comparison; implementing hybrid will not auto-align engineering-judgment rows with Red Hat HTML.
