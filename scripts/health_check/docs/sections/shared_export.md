```bash
make hc-pdf
```

This runs inside the project container (same as `make pdfs` for OCP-V), which has `pandoc` and `weasyprint` already installed. No host dependencies needed beyond `podman` or `docker`.

The flow is identical to the OCP-V pipeline: markdown → `pandoc` (branded CSS + HTML) → `weasyprint` (PDF).

PDFs are written to:
- `output/Health_Check_Report/PDFs/` — customer-facing report (nested reports keep a cluster subdirectory, e.g. `PDFs/<cluster_dir>/…`)

If the container image hasn't been built yet, `make hc-pdf` will build it automatically first.

