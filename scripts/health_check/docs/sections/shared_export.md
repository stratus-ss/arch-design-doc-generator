```bash
make hc-pdf
make hc-pdf REPORT=output/Health_Check_Report/<report>.md
make hc-html REPORT=path.md FORCE=1   # overwrite existing basename dest only
```

This runs inside the project container (same as `make pdfs` for OCP-V), which has `pandoc` and `weasyprint` already installed. No host dependencies needed beyond `podman` or `docker`.

The flow is identical to the OCP-V pipeline: markdown → `pandoc` (branded CSS + HTML) → `weasyprint` (PDF).

PDFs are written to:
- `output/Health_Check_Report/PDFs/` — customer-facing report (nested reports keep a cluster subdirectory, e.g. `PDFs/<cluster_dir>/…`)

HTML is written to:
- `output/Health_Check_Report/HTML/` — collapsible report (`make hc-html`; same `REPORT=` / `FORCE=1` rules)

Unset `REPORT` discovers all report markdown (prefers `_pruned.md`). `REPORT=path.md` exports that one file. A source outside the report tree maps by basename. `FORCE=1` overwrites an existing basename dest.

If the container image hasn't been built yet, `make hc-pdf` will build it automatically first.

