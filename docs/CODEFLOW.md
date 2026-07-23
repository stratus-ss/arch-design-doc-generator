# Arch Design Doc Generator Code Flow

## Table of Contents

1. Setup and project bootstrap
2. HLD AI preparation (`make build-hld-from-adr`)
3. HLD publish pipeline (`make publish`)
4. LLD + work item pipeline (`make build-lld`, `make workitems`)
5. Host vs container execution

---

## 1) Setup and Project Bootstrap

`make setup CLIENT="Example Client" PROJECT="OCP-V"` routes through the container entrypoint and executes `scripts/setup_project.py`.

```mermaid
flowchart TD
    MakeSetup[make setup CLIENT PROJECT] --> Entrypoint[entrypoint.sh cmd_setup]
    Entrypoint --> SetupPy[setup_project.py]
    SetupPy --> CreateYaml[create project.yaml from project.example.yaml]
    SetupPy --> Scaffold[create scaffold directories]
    SetupPy --> ReplaceTokens[replace placeholders in templates]
    SetupPy --> RenameTemplates[copy Template files to client-prefixed files]
    SetupPy --> SummaryFile[create HLD summary file]
    SetupPy --> SeedDiagrams[seed Diagrams phase directories]
```

Key flow details:
- `create_project_yaml()` injects `CLIENT` and `PROJECT` code into generated config.
- `rename_templates()` produces client-specific working copies from `Template_*` files.
- `seed_diagrams()` copies canonical examples into phase folders for editing.

---

## 2) HLD AI Preparation (`make build-hld-from-adr`)

`make build-hld-from-adr` is an alias for `prepare-hld-ai`, which runs `scripts/ai/ai_draft_deterministic.py`.

```mermaid
flowchart TD
    BuildHldFromAdr[make build-hld-from-adr] --> AiDraft[ai_draft_deterministic.py hld]
    AiDraft --> PromptA[Prompt A global extraction]
    PromptA --> PromptB[Prompt B phase extraction]
    PromptB --> PromptC[Prompt C repair loop]
    PromptC --> SlotSchema[slot_schema.json validation]
    SlotSchema --> Render[render.py deterministic template render]
    Render --> WriteBack[write rendered markdown to HLD markdown_files]
```

Data artifacts produced:
- `output/.deterministic/slots/slot_map.json`
- `output/drafts_deterministic/*`
- Updated client HLD markdown files used by downstream publish targets

---

## 3) HLD Publish Pipeline (`make publish`)

`make publish` executes container target `build hld` via `entrypoint.sh`.

```mermaid
flowchart TD
    Publish[make publish] --> BuildHldCmd[entrypoint.sh cmd_build_hld]
    BuildHldCmd --> StitchHld[stitch_hld.sh]
    BuildHldCmd --> ExportDrawio[export_drawio.sh]
    BuildHldCmd --> ExportMermaid[export_mermaid.sh --type hld]
    BuildHldCmd --> DrawioVariants[generate_drawio_variants.py --type hld]
    BuildHldCmd --> PdfHld[generate_pdfs.py --type hld]
    BuildHldCmd --> ValidateTokens[validate_placeholders.py]
    ValidateTokens --> CollectOutputs[collect_outputs to output/]
```

The publish stage generates:
- stitched HLD markdown
- Drawio markdown variants
- HLD diagram PNGs
- HLD PDFs

---

## 4) LLD and Work Item Pipeline

### LLD Build (`make build-lld`)

```mermaid
flowchart TD
    BuildLld[make build-lld] --> BuildLldCmd[entrypoint.sh cmd_build_lld]
    BuildLldCmd --> StitchLld[stitch_lld.sh]
    BuildLldCmd --> ExportMermaidLld[export_mermaid.sh --type lld]
    BuildLldCmd --> DrawioVariantsLld[generate_drawio_variants.py --type lld]
    BuildLldCmd --> PdfLld[generate_pdfs.py --type lld]
    PdfLld --> CollectLldOutputs[collect_outputs to output/LLD]
```

### Work Items (`make workitems`)

```mermaid
flowchart LR
    Workitems[make workitems] --> LldParser[lld_to_workitems.py]
    LldParser --> MarkdownItems[Work item markdown files]
    LldParser --> CsvItems[Jira-style CSV output]
    MarkdownItems --> OutputDir[output/Work_Items]
    CsvItems --> OutputDir
```

---

## 5) Host vs Container Execution

| Command Family | Runtime | Primary scripts |
|---|---|---|
| `setup`, `publish`, `build-lld`, `build`, `workitems` | Container (`entrypoint.sh`) | `scripts/build/*`, `scripts/tools/lld_to_workitems.py` |
| `build-hld-from-adr`, `prepare-hld-ai`, `validate-slots` | Host | `scripts/ai/ai_draft_deterministic.py`, `scripts/ai/deterministic/*` |
| Utility targets (`sanitize-diagrams`, `combine-drawio`, `sample-schedule`) | Host | `scripts/tools/*` |

Operational note:
- Heavy binary dependencies stay containerized.
- AI credentials remain on the host path.
- `output/` is the canonical artifact destination for publishable deliverables.
