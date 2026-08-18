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

`project.yaml` and `slot_map.json` are gitignored at any path — never commit them. `project.example.yaml` is the committed template. Repo-root `ADR/` (filled engagement ADRs) and `output/` (and `output-*/`) are gitignored. ADR **templates** live in `templates/ADR/` (`ADR_template.md`, `ADR_EXAMPLE.md`, `Agenda_template.md`). Copy or let `make setup` place a filled ADR under `ADR/`. From the repo root, `python3 -m pytest tests` collects without setting `PYTHONPATH`.

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
make force-image                    # force rebuild
make push REGISTRY=quay.io/org     # push to a registry
```

## Quick Start

1. `make setup CLIENT="Example Client" PROJECT="OCP-V"` — copies generic templates into `output/` working copies and copies `templates/ADR/ADR_template.md` to `ADR/ADR_<client>.md`. If those files already exist, setup exits with a warning; pass `FORCE=1` to overwrite.
2. Fill in the engagement ADR under `ADR/` (gitignored). Start from `templates/ADR/ADR_template.md` or the worked example `templates/ADR/ADR_EXAMPLE.md`. Do not edit files under `templates/ADR/` for a client engagement.
3. `make build-hld-from-adr` — extracts one `slot_map.json`, applies `project.yaml` `slots:` overlay, and renders **HLD, LLD, and stampable diagrams** into `output/`
4. `make publish`
5. `make build-lld`
6. `make workitems`

Run `make help` or `make status` at any time to see available targets and current readiness.

## Common Targets

| Target | Purpose |
|---|---|
| `make setup CLIENT="..." PROJECT="..."` | Bootstrap `project.yaml` and client working files from `templates/` (refuses overwrite unless `FORCE=1`) |
| `make status` | Show setup/build progress |
| `make build-hld-from-adr` | Extract slots from the ADR and render HLD, LLD, and `output/Diagrams` from the same `slot_map.json` |
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
| `make force-image` | Force rebuild the container image |
| `make check-annotations` | Check HLD mermaid blocks for drawio annotations |
| `make package` | Zip a runnable host copy of the toolkit |
| `make lld-closeness CANONICAL=/path/to/LLD` | Report LLD content closeness vs a canonical fixture (`output/LLD` by default) |
| `make push REGISTRY=...` | Push container image to a registry |
| `make clean` | Reset generated artifacts |

## Health Check collection (host)

A second engagement type (`PROJECT=HC`) provides OpenShift cluster health-check data collection without the HLD/LLD pipeline. Report generation, PDF/HTML output, and AI are **not included** on this branch — a later plan adds those.

| Target | Purpose |
|---|---|
| `make setup CLIENT="..." PROJECT="HC"` | Bootstrap `project.yaml` from `project.example.hc.yaml` and scaffold `output/hc_collect` + `output/Health_Check_Report` |
| `make hc-collect KUBECONFIG=<path>` | Collect cluster JSON via live `oc` CLI |
| `make hc-push-scripts HC_SSH_HOST=user@host` | Push supportshell scripts to a remote server |
| `make hc-collect-remote HC_SSH_HOST=... HC_MG_INPUT=<path>` | Run `hc_collect_multi.sh` on the remote via SSH |
| `make hc-fetch-results HC_SSH_HOST=...` | Fetch results tarball from remote into `output/hc_collect/<date>` |
| `make hc-merge MERGE_INPUTS="dir1 dir2"` | Merge multiple `hc_results` dirs on the host |
| `make clean-hc` | Remove `output/hc_collect` and `output/Health_Check_Report` |

`project.example.hc.yaml` is the HC template; never commit `project.yaml` or kubeconfigs.

## Key Variables

```text
ENGINE              podman | docker
IMAGE               arch-doc-gen (container image name)
CLIENT              "Example Client"
PROJECT             OCP-V (default)
PHASE               phase1 | phase2 | phase3 | phase4
AI_TOOL             cursor | claude | codex
AI_MODEL            model identifier (default: claude-sonnet-4-6)
AI_TIMEOUT          per-call timeout seconds (default: 900)
ADR_MODE            auto | chunked (default: auto = one full-ADR Prompt A, then 8x12k fallback)
REFINE_PHASES       1 to opt in to Prompt B per-phase refine (off by default)
OUTPUT_ROOT         output
FORCE               1 (setup: overwrite working copies; AI: re-extract even if inputs are unchanged)
                    GNU make does not accept --force; use FORCE=1 or `make <target> force`
RUNS                repeatability test iterations (default: 3)
AI_MAX_CHARS        max chars per ADR chunk in chunked mode (default: 12000)
AI_MAX_CHUNKS       max ADR chunks in chunked mode (default: 8)
CANONICAL           path to canonical LLD directory for `make lld-closeness`
CANONICAL_DIR       path to canonical files for AI benchmark mode
REGISTRY            container registry for make push
```

Operator facts the ADR often omits (`CLIENT_DOMAIN`, `GITOPS_HOST`, `REGISTRY_MIRROR`, `REGISTRY_MIRROR_FQDN`, `HUB_CLUSTER_NAME`, `NTP_DOMAIN`) go in `project.yaml` under `slots:`. Non-empty overlay values override extract; empty overlay does not wipe a filled extract. `prepare-hld-ai` always rewrites stampable `.drawio` files into `output/Diagrams`.

## License

This project is licensed under GNU GPLv3. See [LICENSE](LICENSE).
