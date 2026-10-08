# Arch Design Doc Generator

Config-driven document automation toolkit for architecture engagements. It turns a filled
Architecture Decision Record (ADR) into structured High-Level Design (HLD) and Low-Level Design
(LLD) deliverables: stitched markdown, draw.io and mermaid diagrams, branded PDFs, and
sprint-ready work items (Jira-style CSV plus one markdown card per item).

**Domain:** OpenShift Virtualization (OCP-V) platform engineering for VMware → OpenShift
Virtualization migration engagements, organized in 4 phases — Foundation, Platform Build,
Fleet Operations, Migration — covering ACM hub/spoke topology, ZTP provisioning, GitOps
fleet management, and a 3-tier site model.

## Highlights

- **AI-first, deterministic-render pipeline.** An LLM (Cursor SDK, Claude CLI, or Codex CLI)
  extracts ~148 named *slots* from the ADR as strict JSON with evidence envelopes
  (value / confidence / verbatim excerpt / source). Everything else renders
  deterministically: same slot map → hash-identical output, with `{TBD}` for empty slots
  and `${VAR}` shell sequences never substituted.
- **One slot map to rule them all.** A single extraction produces one `slot_map.json`
  that renders HLD, LLD, and diagram stamps — no second AI pass for LLD.
- **Cost-aware AI.** Fingerprint caching (ADR + config + schema + prompts hash) skips
  re-extraction when inputs are unchanged; repeatability is hash-tested.
- **Full diagram pipeline.** 42 sanitized baseline draw.io diagrams stamped with client
  slots, headless draw.io + mermaid PNG export, annotation-pinned and fuzzy
  mermaid↔draw.io mapping, `Drawio_*` markdown variants that swap code blocks for
  images in PDFs, and READOUT asset sync.
- **Traceability built in.** ADR citation locks, per-slot evidence excerpts, `## LLD-NN:`
  section ids, CG-*/AC-* completion-gate and acceptance-criteria rows, and ADR `*(ADR n)*`
  references carried into Jira work items (Epic Link = phase, Labels = ADR ref).
- **Branded deliverables.** Brand colors/fonts from `project.yaml` flow into the PDF
  print CSS (with WeasyPrint bookmarks), the mermaid theme, and diagram exports.
  Default footer: *"Internal — Confidential"*.
- **Migration-ops utilities.** RVTools vInfo XLSX → per-site migration schedule workbook
  with tracking columns, plus a synthetic sample-schedule generator for demos.
- **Security by design.** All client secrets (`project.yaml`, `slot_map.json`, `ADR/`,
  `RVTools/*.xlsx`) are gitignored at any path; the release packager aborts if any
  leak in; diagram sanitizers strip client PII before examples can ship.

## How it works

```text
make setup CLIENT="Example Client" PROJECT="OCP-V"     ← scaffold project.yaml,
        │                                                  client working copies,
        ▼                                                  seeded diagrams, ADR file
  operator fills ADR/<prefix>.md (architecture decisions)
  operator optionally fills project.yaml `slots:` (operator facts)

make build-hld-from-adr          (alias: prepare-hld-ai — HOST, needs AI creds)
        │
        ▼  scripts/hld_lld/ai/ai_draft_deterministic.py hld --extractor ai
slot_cache: fingerprint ADR+config+schema+prompts → skip or extract
  │ Prompt A (auto: single full-ADR call; timeout/parse fail → 8×12k chunked retry)
  │ Prompt B (opt-in REFINE_PHASES=1): per-phase refine against template contracts
  │ project.yaml slots: overlay (non-empty wins; empty never wipes)
  │ empty-required repair (skipped — no model call — when none are empty)
  │ Prompt C: schema repair (≤2 rounds)
  │ validate-slots against the 148-slot schema
        ▼
output/.deterministic/slots/slot_map.json
        │
        ▼  render-phase: {TOKEN} → value | {TBD} (draw.io stamping too)
output/HLD/markdown_files/<Prefix>_OCP-V_HLD_DecisionJourney_*.md   (validated)
output/LLD/<Prefix>_OCP-V_LLD_*.md             (same map, always re-rendered)
output/Diagrams/**/*.drawio                     (stamped; always overwritten)
        │
        ▼  operator reviews/edits diagrams if desired

make publish                     (container: build hld — 6 steps)
        │  stitch → draw.io PNGs → mermaid PNGs → Drawio_* variants
        │  → PDFs → placeholder validation → output/HLD/{PDFs,diagrams}

make build-lld                    (container)
        │  stitch → mermaid PNGs → Drawio_* variants → PDFs → output/LLD

make workitems                    (container)
        │  LLD → output/Work_Items/<Phase>/*.md + summary.csv (Jira-compatible)

make rvtools FILES="RVTools/*.xlsx"   (container)
        │  vInfo → output/Migration_Weekly_Schedule.xlsx (styled, per-site sheets)
```

Shortcuts: `make build` = AI prep + HLD + LLD + work items. `make rebuild` = clean + build.
`make status` reports setup/build readiness; `make help` lists every target.

## Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System components, data flow, runtime boundaries, configuration architecture |
| [docs/CODEFLOW.md](docs/CODEFLOW.md) | The 5 execution paths (setup, AI prep, publish, LLD + work items, utilities) with flowcharts |
| [docs/PROJECT_LAYOUT.md](docs/PROJECT_LAYOUT.md) | Directory tree, naming conventions, generated-vs-source-controlled artifact table |
| [openspec/](openspec/) | Living behavioral specs for the slot pipeline (requirements + scenarios) |

## Repository structure

```text
arch-design-doc-generator/
├── Makefile                      ← primary user interface ("the only interface you need")
├── project.example.yaml          ← committed config template (copied to gitignored project.yaml by setup)
├── pyproject.toml                ← Python ≥3.10, pyyaml only core dep; pytest + ruff for dev
├── ruff.toml                     ← lint: py310 target, line-length 120
├── Containerfile                 ← build image `arch-doc-gen` (Fedora 43 + toolchain)
├── scripts/entrypoint.sh         ← container command router (setup/build/diagrams/pdfs/workitems/rvtools/…)
├── scripts/
│   ├── setup_project.py          ← bootstrap: ProjectType registry, create project.yaml,
│   │                                scaffold dirs, rename/copy templates, seed diagrams
│   ├── setup_status.py           ← 6-step readiness report (setup, ADR fill, slots, HLD, LLD, work items)
│   ├── hld_lld/
│   │   ├── ai/ai_draft_deterministic.py  ← orchestrator: extraction + render + validate
│   │   ├── ai/deterministic/
│   │   │   ├── cli.py            ← subcommands: chunk, extract-ai, validate-slots,
│   │   │   │                        build-contract, build-citation-lock, render-phase,
│   │   │   │                        stitch, validate-hld, inspect-slots/chunks, test-repeatability
│   │   │   ├── slots.py          ← Prompt A/B/C extraction, chunking, yaml overlay, evidence envelopes
│   │   │   ├── slot_schema.json  ← 148-slot strict schema (preamble 5, phase1 21, phase2 25,
│   │   │   │                        phase3 9, phase4 11, appendix 6, lld 42)
│   │   │   ├── slot_cache.py     ← fingerprint skip logic (avoids surprise model cost)
│   │   │   ├── slot_validate.py  ← schema + required-slot validation
│   │   │   ├── render.py         ← deterministic {TOKEN} substitution, contracts, citation locks,
│   │   │   │                        drift detection
│   │   │   ├── markdown_utils.py ← placeholder regex (protects ${SHELL} vars), tier defaults,
│   │   │   │                        registry-mirror policy, draw.io stamping helpers
│   │   │   └── prompts/          ← extract_hld_slots_{global,phase,repair,empty}.md
│   │   ├── build/
│   │   │   ├── stitch_hld.sh / stitch_lld.sh   ← stitchmd assembly of combined docs
│   │   │   ├── export_drawio.sh / export_mermaid.sh  ← headless diagram → PNG export
│   │   │   ├── generate_drawio_variants.py     ← Drawio_*.md (mermaid blocks → draw.io PNG links)
│   │   │   ├── generate_pdfs.py                ← pandoc + weasyprint branded PDFs
│   │   │   └── check_annotations.py            ← audit of <!-- drawio: … --> annotations
│   │   ├── lld_to_workitems.py   ← LLD sections → per-item markdown cards + Jira CSV
│   │   └── report_lld_closeness.py ← LLD content-closeness report vs canonical fixtures
│   ├── shared/
│   │   ├── lib/
│   │   │   ├── ai_invoke.py      ← unified Cursor/Claude/Codex invocation, SDK bootstrap,
│   │   │   │                        retry/backoff, heartbeat
│   │   │   ├── config.py         ← project.yaml loading, dot-path queries, branded PDF CSS
│   │   │   ├── client_prefix.py  ← derive client file prefix ('Example Client'→'Example')
│   │   │   ├── diagram_layout.py ← phase/top-level diagram prefixes, slugify
│   │   │   └── validate_placeholders.py ← fails on unresolved {PLACEHOLDER} (except {TBD})
│   │   └── tools/
│   │       ├── combine_drawio.py ← merge .drawio files into one multi-tab file
│   │       ├── sanitize_diagrams.py / sanitize_diagrams_data.py ← strip client PII from diagrams
│   │       └── package_release.sh ← distributable zip + secrets sanity check (fail-closed)
│   └── rvtools/
│       ├── rvtools_to_schedule.py ← RVTools vInfo XLSX → per-site migration schedule workbook
│       └── generate_sample_schedule.py ← synthetic demo schedule (safe for the public repo)
├── templates/
│   ├── ADR/                      ← ADR_template.md (65 decision entries), ADR_EXAMPLE.md,
│   │                                Agenda_template.md (60-min discussion agenda)
│   ├── HLD/markdown_files/       ← "Decision Journey" narrative: main + preamble +
│   │                                phase1–4 chapters + appendix + stitch summary
│   ├── LLD/                      ← 5 phase templates (Foundation, ACM Hub, Platform Build,
│   │                                Fleet Operations, Migration) + examples/Sample_A–H
│   │                                (component spec, runbook, build sheet, traceability,
│   │                                tier profile, layered architecture, GitOps catalog, blended)
│   └── Diagrams/examples/        ← 42 sanitized baseline .drawio files (HLD top-level +
│                                    phase1–4 flows + LLD layer models), all {TOKEN}-stamped
├── docs/                         ← ARCHITECTURE.md, CODEFLOW.md, PROJECT_LAYOUT.md
├── openspec/                     ← slot-pipeline spec (requirements + scenarios) +
│                                    archived change proposals
├── tests/                        ← 10 functional test modules (ai_invoke, extraction,
│                                    render, sanitize, setup, slot cache, tier defaults,
│                                    HLD validation, workitems; conftest.py)
├── RVTools/                      ← drop client RVTools XLSX exports here (gitignored; .gitkeep only)
├── LICENSE                       ← GNU GPLv3
└── NOTICE                          ← third-party tool attribution
```

## Prerequisites

| For | Needs |
|---|---|
| Host AI targets (`build-hld-from-adr`, `prepare-hld-ai`) | `python3`, `pyyaml`, AI tooling (`cursor-sdk` or selected CLI) |
| Container targets (`setup`, `publish`, `build-lld`, `workitems`) | `podman` or `docker`, `make` |

Podman is auto-detected; override with `ENGINE=docker` if needed.

`project.yaml` and `slot_map.json` are gitignored at any path — never commit them.
`project.example.yaml` is the committed template. Repo-root `ADR/` (filled engagement ADRs)
and `output/` (and `output-*/`) are gitignored. ADR **templates** live in `templates/ADR/`;
copy or let `make setup` place a filled ADR under `ADR/`.
From the repo root, `python3 -m pytest tests` collects without setting `PYTHONPATH`.

## Container image

Most pipeline targets run inside a container built from the `Containerfile`. The image
(`arch-doc-gen`, Fedora 43 base) bundles everything the pipeline needs so the host only
requires a container engine:

- **pandoc** — markdown to intermediate formats
- **weasyprint 66.0** — HTML/CSS to PDF (print CSS rendered from `brand:` config)
- **stitchmd v0.9.0** — multi-file markdown assembly
- **drawio-desktop 26.2.2** — `.drawio` diagram export (headless via xvfb)
- **mermaid-cli 11.16.0** — mermaid diagram rendering (brand-themed)
- **Python 3 + pyyaml 6.0.3 + openpyxl 3.1.5** — scripting and spreadsheet generation

The image is built automatically on first use of any container target, and auto-rebuilt
when scripts change (the image embeds a scripts hash). To build or rebuild manually:

```bash
make image                          # build if not present
make force-image                    # force rebuild
make push REGISTRY=quay.io/org      # push to a registry
```

## Quick start

1. `make setup CLIENT="Example Client" PROJECT="OCP-V"` — copies generic templates into
   `output/` working copies and copies `templates/ADR/ADR_template.md` to
   `ADR/ADR_<client>.md`. If those files already exist, setup exits with a warning; pass
   `FORCE=1` to overwrite.
2. Fill in the engagement ADR under `ADR/` (gitignored). Start from `templates/ADR/ADR_template.md`
   or the worked example `templates/ADR/ADR_EXAMPLE.md`. Do not edit files under `templates/ADR/`
   for a client engagement.
3. `make build-hld-from-adr` — extracts one `slot_map.json`, applies `project.yaml`
   `slots:` overlay, and renders **HLD, LLD, and stampable diagrams** into `output/`.
4. `make publish` — HLD outputs (stitch, diagrams, PDFs).
5. `make build-lld` — LLD outputs.
6. `make workitems` — sprint work items from LLD.

Run `make help` or `make status` at any time to see available targets and current readiness.

## Make targets

| Target | Purpose |
|---|---|
| `make setup CLIENT="…" PROJECT="…"` | Bootstrap `project.yaml` and client working files from `templates/` (refuses overwrite unless `FORCE=1`) |
| `make status` | Show setup/build progress (6-step health report) |
| `make build-hld-from-adr` | Extract slots from the ADR and render HLD, LLD, and `output/Diagrams` from the same `slot_map.json` |
| `make publish` | Build HLD outputs (stitch, diagrams, PDFs) |
| `make prepare-and-publish` | AI prep then publish HLD in one step |
| `make build-lld` | Build LLD outputs (stitch, diagrams, PDFs) |
| `make diagrams` | Export all diagrams (.drawio + mermaid) to PNG |
| `make pdfs` | Regenerate PDFs only (skip diagram export) |
| `make workitems` | Extract sprint work items from LLD (markdown cards + Jira CSV) |
| `make rvtools FILES="…"` | Process RVTools XLSX into a migration schedule workbook |
| `make sample-schedule` | Generate a synthetic demo schedule (safe sample data) |
| `make build` | Full pipeline (AI + HLD + LLD + work items) |
| `make rebuild` | Clean then full rebuild |
| `make lld-closeness CANONICAL=/path/to/LLD` | Report LLD content closeness vs a canonical fixture |
| `make check-annotations` | Audit HLD mermaid blocks for draw.io annotations (fails on broken ones) |
| `make combine-drawio` | Merge `.drawio` files into one multi-tab file |
| `make sanitize-diagrams` | Strip client references from diagrams (in-place by default) |
| `make package` | Zip a runnable host copy of the toolkit (fail-closed secrets check) |
| `make inspect-slots` / `inspect-chunks` | Diagnostics on the slot pipeline |
| `make validate-slots` | Validate the slot map against the 148-slot schema |
| `make test-hld-ai-repeatability RUNS=3` | Determinism check: hash outputs across runs, fail on drift |
| `make image` | Build the container image (auto-built on first use) |
| `make force-image` | Force rebuild the container image |
| `make push REGISTRY=…` | Push container image to a registry |
| `make clean` | Reset generated artifacts (plus `clean-hld`, `clean-lld`, `clean-pdfs`, `clean-diagrams`, `clean-workitems`, `clean-ai`, `clean-setup`) |

## Configuration

`project.yaml` (created from `project.example.yaml` by `make setup`) controls identity,
branding, phases, paths, and the slot overlay:

- **Identity** — `client_name`, `project_code` (`OCP-V`), HLD/LLD document titles.
- **Brand** — `primary_color` `#003366`, `secondary_color` `#005195`, header/code fonts,
  footer text (default `"Internal — Confidential"`); flows into PDF CSS and the mermaid theme.
- **Phases** — 5 entries with yaml ids (`phase1`, `phase1-hub`, `phase2`, `phase3`, `phase4`);
  note `lld_to_workitems.py --phases N` keys by yaml id, not list index.
- **HLD/LLD/Diagrams/paths** — file maps, combined outputs, phase diagram dirs, working paths.
- **Registry mirror policy** — `unset` | `same_as_image_registry` | `distinct`.
- **`slots:` overlay** — operator facts the ADR often omits (`CLIENT_DOMAIN`,
  `GITOPS_HOST`, `REGISTRY_MIRROR`, `REGISTRY_MIRROR_FQDN`, `HUB_CLUSTER_NAME`,
  `NTP_DOMAIN`). Non-empty overlay values override extraction; empty overlay does not wipe
  a filled extract.

Key environment variables:

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

`prepare-hld-ai` always rewrites stampable `.drawio` files into `output/Diagrams`.

## AI slot pipeline

The pipeline's contract: **the AI only extracts facts into JSON; all rendering is deterministic.**

1. **Chunking** — the ADR is split into heading-aware chunks (default: one full-ADR
   single pass; `ADR_MODE=chunked`: 12k-char chunks, max 8).
2. **Prompt A (global extraction)** — strict JSON-only extraction into the 148-slot
   schema; every slot carries an evidence envelope: `value`, `confidence`
   (`high`/`medium`/`low`), `evidence_excerpt` (verbatim, <120 chars), `evidence_source`.
   Values are merged across chunks by confidence; the model must never invent values.
3. **Prompt B (opt-in refine)** — per-phase refine against the template contract
   (`REFINE_PHASES=1`).
4. **Overlay** — non-empty `project.yaml` `slots:` values override extraction.
5. **Empty-required repair** — one targeted call for empty required slots; skipped
   entirely (no model call) when none are empty.
6. **Prompt C (schema repair)** — up to 2 repair rounds to fix schema validation errors.
7. **Validate + render** — `validate-slots` checks the schema; `render-phase` substitutes
   `{TOKEN}` placeholders (empties become `{TBD}`); contracts (template heading/table
   structure) and citation locks must match; drift detection fails on non-determinism.

Fingerprint caching (`slot_cache.py`) hashes ADR files, `project.yaml`, the schema, the
prompts, and the placeholder set into one SHA-256: if nothing changed, extraction is
skipped (no surprise model cost); `FORCE=1` forces it.

Host vs container split: AI extraction and diagnostics run on the **host** (needs AI
credentials — e.g. `CURSOR_API_KEY`); stitching, diagram export, PDF generation,
work items, and RVTools run in the **container**, so the host needs no binary toolchain.

## Templates

- **ADR** (`templates/ADR/`) — `ADR_template.md` with 65 numbered decision entries grouped
  by topic (installation & provisioning, networking, storage, security, observability,
  backup/DR, identity, GitOps, migration…), each with `Issue`, blank `Decision`, `Status`,
  `Assumptions`, `Argument`; `ADR_EXAMPLE.md` worked example; `Agenda_template.md`
  (60-minute discussion agenda).
- **HLD** (`templates/HLD/markdown_files/`) — the "Decision Journey" narrative:
  decisions in deployment order with flow narrative, mermaid diagrams with
  `{PLACEHOLDER}` tokens, and gate-criteria checklists (main, preamble, phase1–4
  chapters, appendix, stitch summary).
- **LLD** (`templates/LLD/`) — 5 phase templates (Foundation, ACM Hub Deployment,
  Platform Build, Fleet Operations, Migration) with document control, `## LLD-NN:`
  sections (prerequisites, completion gates, dependencies, implementation procedure,
  acceptance criteria, tier variance); `examples/` holds Samples A–H format references
  (component specification, runbook, build sheet, decision traceability, tier site
  profile, layered architecture, GitOps manifest catalog, blended).
- **Diagrams** (`templates/Diagrams/examples/`) — 42 sanitized baseline `.drawio`
  files, all `{TOKEN}`-stamped, no client PII: 19 top-level HLD diagrams (ACM hub,
  backup/DR, GitOps automation, network/storage/observability, RBAC…), phase1–4 flow
  diagrams, and LLD layer-model + implementation-flow diagrams.

## Diagram pipeline

`prepare-hld-ai` stamps `{TOKEN}` placeholders in the example diagrams with extracted
slots (`${TOKEN}` shell sequences are preserved). Then:

- `export_drawio.sh` — headless draw.io → PNG (sidecar PNGs, synced to `HLD/READOUT/assets`).
- `export_mermaid.sh` — mermaid blocks → brand-themed PNGs (skips blocks with
  unresolved `{PLACEHOLDER}`/`{TBD}`).
- `generate_drawio_variants.py` — builds `Drawio_*.md` variants where each mermaid block
  is replaced by a linked draw.io PNG. Resolution order: explicit
  `<!-- drawio: FILENAME -->` annotation → 4-level fuzzy match → mermaid PNG fallback.
  Use `make check-annotations` to audit the annotations.
- `generate_pdfs.py` — pandoc → branded HTML → WeasyPrint PDFs (letter page, branded
  header/footer, PDF bookmarks); mermaid blocks are swapped for rendered PNGs.

## Testing

```bash
python3 -m pytest tests        # collects without setting PYTHONPATH (pyproject configures it)
```

10 functional test modules cover: Claude-CLI invocation argv and JSON unwrapping,
single-pass Prompt A chunking and overlay semantics, draw.io stamping (`{TOKEN}` fills,
`${TOKEN}` preserved), render `${SHELL}` protection and `{TBD}` empties, sanitize
`--from-output --yes` guard, full `make setup` flow (incl. fail-closed overwrite),
slot-cache fingerprint decisions, tier defaults edge cases, HLD validation/drift,
and LLD→work-items end to end (`--phases 4` keying by yaml id).

## OpenSpec

[openspec/specs/hld-lld-slot-pipeline/spec.md](openspec/specs/hld-lld-slot-pipeline/spec.md)
is the living behavioral spec: one slot map renders HLD+LLD; `$`-prefixed braces
untouched; empty slots → `{TBD}`; setup fail-closed; templates contain no client PII
(scenarios explicitly scan for real-engagement terms); sanitize in-place by default;
work-item `--phases` keys by yaml id; registry-mirror policy; Prompt A single-pass with
chunked fallback; Prompt B opt-in; overlay nonempty-override / empty-no-wipe;
fingerprint-fresh skip still binds overlay + render.

## Security

Client material is never committed: `project.yaml`, `slot_map.json`, `/ADR/`,
`output*/`, and `RVTools/*.xlsx` are gitignored at any path. `package_release.sh`
runs a secrets sanity check and aborts if client files, credentials, or non-`Template_`
scaffold files are found in the distributable. `sanitize_diagrams.py` /
`sanitize_diagrams_data.py` replace client references in diagrams with generic
`{PLACEHOLDER}` tokens before they can become shipped examples.

## License

This project is licensed under GNU GPLv3. See [LICENSE](LICENSE).
Third-party tools are attributed in [NOTICE](NOTICE).
