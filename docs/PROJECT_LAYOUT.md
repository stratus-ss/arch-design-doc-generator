# Arch Design Doc Generator Project Layout

## Repository Tree

```text
.
├── ADR/
│   ├── ADR_template.md
│   └── Agenda_template.md
├── Diagrams/
│   ├── examples/
│   └── *.drawio
├── HLD/
│   └── markdown_files/
│       ├── Template_OCP-V_HLD_DecisionJourney_*.md
│       └── Template_summary.md
├── LLD/
│   ├── Template_OCP-V_LLD_*.md
│   └── examples/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CODEFLOW.md
│   └── PROJECT_LAYOUT.md
├── scripts/
│   ├── ai/
│   │   ├── ai_draft_deterministic.py
│   │   └── deterministic/
│   ├── build/
│   ├── lib/
│   ├── tools/
│   ├── entrypoint.sh
│   ├── requirements.txt
│   └── setup_project.py
├── Containerfile
├── Makefile
├── project.example.yaml
└── README.md
```

## Directory Responsibilities

### `ADR/`
- Templates for decision capture sessions.
- Source input for deterministic AI extraction and HLD slot filling.

### `HLD/markdown_files/`
- Canonical HLD templates that define architecture decisions by phase.
- `Template_summary.md` controls stitching order for template combined output.

### `LLD/`
- Canonical implementation templates by phase.
- Inputs for downstream work item generation.

### `Diagrams/`
- Root-level architecture diagrams used during publish.
- `examples/` is the sanitized and source-controlled baseline.
- `phase1..phase4/` folders are generated during setup for working copies.

### `scripts/lib/`
- Shared config and helper layer.
- `config.py` parses `project.yaml`.
- `common.sh` exposes config accessors to bash scripts.

### `scripts/ai/`
- Host-only deterministic extraction and render workflow.
- Prompt templates live in `scripts/ai/deterministic/prompts/`.

### `scripts/build/`
- Container-executed build flow:
  - stitch markdown
  - export diagrams
  - generate drawio variants
  - generate PDFs

### `scripts/tools/`
- Auxiliary utilities:
  - LLD to sprint work items
  - RVTools conversion
  - diagram sanitization and merge
  - sample schedule generation

## Key Files

| File | Purpose |
|---|---|
| `Makefile` | Primary user interface for all workflows |
| `scripts/entrypoint.sh` | Container command router |
| `scripts/setup_project.py` | Setup, file generation, and status checks |
| `scripts/ai/ai_draft_deterministic.py` | Deterministic AI orchestration |
| `scripts/lib/config.py` | Unified config reader |
| `project.example.yaml` | Base config template copied to `project.yaml` |

## Naming Conventions

- Template source files: `Template_<PROJECT>_...`
- Generated client files: `<ClientPrefix>_<PROJECT>_...`
- Diagram variants: `Drawio_*.md`
- Combined outputs: `*_combined.md` / `*_Combined.md`

## Generated vs Source-Controlled Artifacts

Source-controlled:
- Templates in `ADR/`, `HLD/`, `LLD/`
- Sanitized diagram examples in `Diagrams/examples/`
- All scripts and docs

Generated during setup/build:
- `project.yaml`
- Client-prefixed HLD/LLD/ADR files
- `output/` build artifacts
- `Diagrams/phase1..phase4/` seeded working directories
- PDFs, PNG exports, and work item outputs
