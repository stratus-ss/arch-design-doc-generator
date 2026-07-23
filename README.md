# Arch Design Doc Generator

Config-driven document automation toolkit for architecture engagements. It turns ADR decisions into structured HLD/LLD artifacts, diagrams, PDFs, and sprint-ready work items.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - system components, data flow, and runtime boundaries
- [Code Flow](docs/CODEFLOW.md) - execution paths for setup, AI preparation, publish, and work item generation
- [Project Layout](docs/PROJECT_LAYOUT.md) - directory structure and file-level responsibilities

## Prerequisites

| For | Needs |
|---|---|
| Host AI targets (`build-hld-from-adr`, `prepare-hld-ai`) | `python3`, `pyyaml`, AI tooling (`cursor-sdk` or selected CLI) |
| Container targets (`setup`, `publish`, `build-lld`, `workitems`) | `podman` or `docker`, `make` |

Podman is auto-detected; override with `ENGINE=docker` if needed.

## Container Image

Most pipeline targets run inside a container built from the `Containerfile`. The image (`arch-doc-gen`) bundles everything the pipeline needs so the host only requires a container engine:

- **pandoc** — markdown to intermediate formats
- **weasyprint** — HTML/CSS to PDF
- **stitchmd** — multi-file markdown assembly
- **drawio-desktop** — `.drawio` diagram export (headless via xvfb)
- **mermaid-cli** — mermaid diagram rendering
- **Python 3 + pyyaml/openpyxl** — scripting and spreadsheet generation

The image is built automatically on first use of any container target. To build or rebuild manually:

```bash
make image                          # build if not present
podman build -t arch-doc-gen .      # force rebuild
make push REGISTRY=quay.io/org     # push to a registry
```

## Quick Start

1. `make setup CLIENT="Example Client" PROJECT="OCP-V"`
2. Fill in your ADR at `ADR/<client>.md`
3. `make build-hld-from-adr`
4. `make publish`
5. `make build-lld`
6. `make workitems`

Run `make help` or `make status` at any time to see available targets and current readiness.

## Common Targets

| Target | Purpose |
|---|---|
| `make setup CLIENT="..." PROJECT="..."` | Bootstrap project config and client working files |
| `make status` | Show setup/build progress |
| `make build-hld-from-adr` | Run deterministic AI extraction and HLD write-back |
| `make publish` | Build HLD outputs (stitch, diagrams, PDFs) |
| `make prepare-and-publish` | AI prep then publish HLD in one step |
| `make build-lld` | Build LLD outputs (stitch, diagrams, PDFs) |
| `make diagrams` | Export all diagrams (.drawio + mermaid) to PNG |
| `make pdfs` | Regenerate PDFs only (skip diagram export) |
| `make workitems` | Extract sprint work items from LLD |
| `make rvtools` | Process RVTools XLSX into migration schedule |
| `make build` | Full pipeline (AI + HLD + LLD + work items) |
| `make rebuild` | Clean then full rebuild |
| `make image` | Build the container image (auto-built on first use) |
| `make push REGISTRY=...` | Push container image to a registry |
| `make clean` | Reset generated artifacts |

## Key Variables

```text
ENGINE              podman | docker
IMAGE               arch-doc-gen (container image name)
CLIENT              "Example Client"
PROJECT             OCP-V (default)
PHASE               phase1 | phase2 | phase3 | phase4
AI_TOOL             cursor | claude | codex
AI_MODEL            model identifier
OUTPUT_ROOT         output
FORCE               1 (overwrite existing AI drafts)
RUNS                repeatability test iterations (default: 3)
AI_MAX_CHARS        max chars per ADR chunk (default: 12000)
AI_MAX_CHUNKS       max ADR chunks for Prompt A (default: 8)
CANONICAL_DIR       path to canonical files for benchmark mode
REGISTRY            container registry for make push
```

## License

This project is licensed under GNU GPLv3. See [LICENSE](LICENSE).
