KB documentation URLs live in the TOML knowledge base. This repo reviews them with `make hc-link-review` (suggest + HTTP check). After reviewing the CSV, `make hc-link-apply` writes `REPLACE` rows whose evidence contains `HTTP 200` into `[checks.links]` only. It does not rewrite recommendation text.

**When to run:** Before delivering a report, or after editing `scripts/health_check/hc_report/kb/*.toml`.

```bash
    make hc-link-review
    # optional: HC_DOCS_ROOT=/path/to/openshift_documentation HC_LINK_REVIEW_OUT=agent_planning/execution/hc_kb_link_precision
    make hc-link-apply
```

Requires a local OpenShift docs checkout (`HC_DOCS_ROOT`, default `~/git_projects/openshift_documentation`) and a toolkit image with `curl_cffi`. Output is `kb_link_review.md` plus `kb_link_review.csv` under `HC_LINK_REVIEW_OUT`. Suggested URLs never invent `#` fragments.

Apply is fail-closed: missing CSV or a stale `current_url` exits non-zero and does not write that TOML file.
