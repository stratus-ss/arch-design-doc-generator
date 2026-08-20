# Arch Design Doc Generator Project Layout

## Repository Tree

```text
.
├── templates/                          # canonical generic sources (git-tracked)
│   ├── ADR/
│   ├── Diagrams/examples/
│   ├── Health_Check/
│   ├── HLD/markdown_files/
│   └── LLD/
├── ADR/                                # filled engagement ADR (gitignored; not templates)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CODEFLOW.md
│   └── PROJECT_LAYOUT.md
├── scripts/
│   ├── hld_lld/
│   │   ├── ai/
│   │   ├── build/
│   │   ├── lld_to_workitems.py
│   │   └── report_lld_closeness.py
│   ├── health_check/
│   │   ├── collect/
│   │   ├── supportshell/
│   │   ├── hc_report/
│   │   ├── generate_report.py
│   │   ├── hc_investigate.py
│   │   ├── hc_skip_summary.py
│   │   └── generate_command_reference.py
│   ├── shared/
│   │   ├── lib/
│   │   └── tools/
│   ├── rvtools/
│   ├── entrypoint.sh
│   └── setup_project.py
├── openspec/
│   └── specs/hld-lld-slot-pipeline/spec.md
├── tests/
├── output/                             # generated (gitignored; not a template source)
├── Containerfile
├── Makefile
├── project.example.yaml                # committed template; project.yaml is gitignored
└── README.md
```

## Directory Responsibilities

### `templates/`
- Canonical public templates. No client names, authors, or engagement hostnames.
- `templates/HLD/markdown_files/` — HLD phase templates and stitch summary.
- `templates/LLD/` — LLD phase templates and examples.
- `templates/ADR/` — git-tracked ADR and agenda templates (`ADR_template.md`, `ADR_EXAMPLE.md`, `Agenda_template.md`).
- `templates/Diagrams/examples/` — sanitized diagram baseline.
- `templates/Health_Check/` — Health Check report template (`Template_HC_Report.md`).

### `ADR/`
- Filled engagement ADR working copy. Gitignored in full (`/ADR/` — repo-root only so `templates/ADR/` stays tracked).
- `make setup` copies `templates/ADR/ADR_template.md` to `ADR/ADR_<client>.md`. Place the completed ADR here; do not commit it.
- Source input for deterministic AI extraction.

### `output/`
- Generated working copies and build artifacts. Not a template source.
- Gitignored as `output/` and `output-*/` (alternate roots such as `output-claude/` are never committed).
- `output/HLD/markdown_files/` — client-prefixed HLD files (setup copy, then slot render).
- `output/LLD/` — client-prefixed LLD files (setup copy, then slot render).
- `output/.deterministic/slots/slot_map.json` — unified slot map for HLD and LLD (also gitignored at any path as `**/slot_map.json`).
- `output/.deterministic/slots/slot_map.fingerprint.json` — input hashes used to skip or re-run extraction.
- PDFs, PNG exports, and work items also land here.

### `docs/`
- Architecture, code flow, and this layout reference.

### `scripts/health_check/`
- Health Check collection, deterministic report engine, and operator tools.
- `collect/` — live `oc` collectors (`hc_collect.sh`, `lib/common.sh`, category scripts `03`–`12`).
- `supportshell/` — offline `omc` collectors, `hc_merge.py`, `hc_collect_multi.sh`.
- `hc_report/` — report engine:
  - `evaluators/` — 12 category evaluator modules (`platform`, `topology`, `components` plus `components_infra` / `components_network` / `components_misc`, `layered`, `health`, `day2`, `security`, `metrics`, `hardware`) plus `_common.py` and `_shared_checks.py`.
  - `kb/` — TOML knowledge base (`7_1`–`7_9` plus `versions.toml`).
  - `parity.py`, `tsr_parser.py`, `_text.py`, `build_crosswalk_catalog.py` — TSR/CCX catalog expansion, HTML parse, catalog rebuild.
  - `catalogs/` — `tsr_ccx_crosswalk.json`.
  - `registry.py`, `findings.py`, `notes.py`, `renderer.py`, `cli.py`, `kb_loader.py` — pipeline after load.
  - `models.py`, `loader.py`, `metadata.py` — collected JSON models, load, and cluster metadata.
- `generate_report.py` — thin entrypoint (`from hc_report import main`).
- `hc_link_review.py` — CLI that produces a suggested-URL CSV/markdown from KB TOML links and a local docs tree.
  - `hc_report/link_review/` — models, URL parser, docs index, product-routing matcher, and report writer.
- `hc_investigate.py` — trace a finding or check to raw evidence.
- `hc_skip_summary.py` — summarize skipped collection commands.
- `generate_command_reference.py` — markdown reference of collection commands.
- `hc_fetch_results.sh` — fetch results from remote.
- `mg_short_names.yaml` — must-gather short-name resolution.

### `scripts/shared/lib/`
- Shared config and helper layer.
- `config.py` parses `project.yaml`.
- `common.sh` exposes config accessors to bash scripts.

### `scripts/hld_lld/ai/`
- Host-only deterministic extraction and render workflow.
- Prompt templates live in `scripts/hld_lld/ai/deterministic/prompts/`.

### `scripts/hld_lld/build/`
- Container-executed build flow:
  - stitch markdown
  - export diagrams
  - generate drawio variants
  - generate PDFs
  - check mermaid drawio annotations

### `scripts/hld_lld/lld_to_workitems.py`
- LLD to sprint work items.

### `scripts/hld_lld/report_lld_closeness.py`
- Content-closeness report vs a canonical LLD fixture (`make lld-closeness`).

### `scripts/rvtools/`
- RVTools conversion and sample schedule generation.

### `scripts/shared/tools/`
- Diagram sanitization, drawio merge, and release packaging.

### `openspec/`
- Living behavioral specs for this toolkit. Slot-pipeline contract: `specs/hld-lld-slot-pipeline/spec.md`.

## Key Files

| File | Purpose |
|---|---|
| `Makefile` | Primary user interface for all workflows |
| `scripts/entrypoint.sh` | Container command router |
| `scripts/setup_project.py` | Setup, file generation, and status checks |
| `scripts/hld_lld/ai/ai_draft_deterministic.py` | Deterministic AI orchestration (HLD + LLD render) |
| `scripts/shared/lib/config.py` | Unified config reader |
| `project.example.yaml` | Base config template copied to `project.yaml` (gitignored at any path; never commit `project.yaml` or `slot_map.json`) |
| `project.example.hc.yaml` | Health Check config template (used when `PROJECT=HC`) |

## Naming Conventions

- Template source files: `Template_<PROJECT>_...` under `templates/`
- Generated client files: `<ClientPrefix>_<PROJECT>_...` under `output/`
- Diagram variants: `Drawio_*.md`
- Combined outputs: `*_combined.md` / `*_Combined.md`

## Generated vs Source-Controlled Artifacts

Source-controlled:
- Generic templates in `templates/`
- Scripts, tests, and docs
- OpenSpec under `openspec/specs/`

Generated during setup/build (gitignored; never commit):
- `project.yaml` (any directory)
- `slot_map.json` / `slot_map.fingerprint.json` (any directory)
- Client-prefixed files under `output/` and `output-*/`
- Entire repo-root `ADR/` directory (filled ADRs; templates remain in `templates/ADR/`)
- `RVTools/` workbooks and `*.xlsx`
- `Diagrams/phase1..phase4/` seeded working directories
- PDFs, PNG exports, and work item outputs
- `output/hc_collect/` — collected Health Check JSON (gitignored via `output/`)
- `output/Health_Check_Report/` — generated Health Check markdown and audit JSON (gitignored via `output/`)
- `output/tsr_html/` — optional TSR HTML drop directory for `make hc-report` discovery
- `**/kubeconfig`, `**/kubeconfig.*`, `**/.kube/` — kubeconfigs (gitignored)
