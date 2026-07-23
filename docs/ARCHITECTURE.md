# Arch Design Doc Generator Architecture

## Component Flow

```mermaid
flowchart LR
    Makefile[Makefile Targets] --> Setup[setup_project.py]
    Makefile --> HostAI[Host AI Pipeline]
    Makefile --> ContainerBuild[Container Build Pipeline]

    Setup --> ProjectYaml[project.yaml]
    ProjectYaml --> ConfigPy[scripts/lib/config.py]
    ConfigPy --> BashHelpers[scripts/lib/common.sh]

    HostAI --> SlotExtract[slots.py]
    SlotExtract --> Render[render.py]
    Render --> HldMarkdown[HLD markdown files]

    ContainerBuild --> StitchHld[stitch_hld.sh]
    ContainerBuild --> StitchLld[stitch_lld.sh]
    ContainerBuild --> ExportDiagrams[export_drawio.sh + export_mermaid.sh]
    ContainerBuild --> GeneratePdfs[generate_pdfs.py]
    ContainerBuild --> Workitems[lld_to_workitems.py]

    StitchHld --> OutputArtifacts[output/ artifacts]
    StitchLld --> OutputArtifacts
    ExportDiagrams --> OutputArtifacts
    GeneratePdfs --> OutputArtifacts
    Workitems --> OutputArtifacts
```

## Data Pipeline

```mermaid
flowchart TD
    AdrInput[ADR template + project ADR] --> PromptGlobal[Prompt A global extraction]
    PromptGlobal --> PromptPhase[Prompt B phase refinement]
    PromptPhase --> PromptRepair[Prompt C schema repair]
    PromptRepair --> SlotMap[slot_map.json]
    SlotMap --> RenderTemplates[Template render write-back]
    RenderTemplates --> StitchDocs[HLD and LLD stitching]
    StitchDocs --> DrawioVariants[Drawio markdown variants]
    DrawioVariants --> Pdfs[Pandoc and WeasyPrint PDFs]
    StitchDocs --> WorkitemsOut[Work item markdown and CSV]
```

## Runtime Boundaries

| Layer | Runs on | Responsibilities |
|---|---|---|
| Setup | Host + container entrypoint | Generate `project.yaml`, seed project files |
| AI extraction | Host | ADR chunking, slot extraction, deterministic render |
| Build and publish | Container | Stitch markdown, export diagrams, generate PDFs |
| Utilities | Host or container | Diagram sanitization, drawio merge, RVTools conversion |

## Configuration Architecture

- `project.example.yaml` is the template configuration committed to git.
- `make setup CLIENT="..." PROJECT="..."` creates `project.yaml` for a specific engagement.
- `scripts/lib/config.py` is the single configuration adapter used by Python and bash workflows.
- `scripts/lib/common.sh` bridges bash scripts to the same config source.

## Key Dependencies

- **Core runtime:** Python 3, PyYAML, make
- **Containerized build toolchain:** pandoc, weasyprint, draw.io export tooling, mermaid-cli, stitchmd
- **AI path:** Cursor SDK (or compatible CLI path selected via `AI_TOOL`)

## Related Documentation

- [Code Flow](CODEFLOW.md) - execution paths through setup, AI, build, and publishing
- [Project Layout](PROJECT_LAYOUT.md) - directory and file reference for maintainers
