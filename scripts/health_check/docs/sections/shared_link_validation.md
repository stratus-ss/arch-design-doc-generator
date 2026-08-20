KB documentation URLs live in the TOML knowledge base. This repo reviews them with `make hc-link-review` (suggest + HTTP check). It does **not** rewrite TOMLs.

**When to run:** Before delivering a report, or after editing `scripts/health_check/hc_report/kb/*.toml`.

```bash
    make hc-link-review
    # optional: HC_DOCS_ROOT=/path/to/openshift_documentation HC_LINK_REVIEW_OUT=agent_planning/execution/hc_kb_link_precision
```

Requires a local OpenShift docs checkout (`HC_DOCS_ROOT`, default `~/git_projects/openshift_documentation`) and a toolkit image with `curl_cffi`. Output is `kb_link_review.md` plus `kb_link_review.csv` under `HC_LINK_REVIEW_OUT`. Suggested URLs never invent `#` fragments.

TOML write-back is a later plan (`link_review/finalize.py`). Until then, apply accepted URLs by hand.
