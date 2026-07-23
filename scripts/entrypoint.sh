#!/usr/bin/env bash
#
# entrypoint.sh — Container entrypoint for Arch Design Doc Generator.
#
# Routes subcommands to the correct pipeline scripts.
# All paths are relative to /workspace (the bind-mounted project root).

set -euo pipefail

WORKSPACE="/workspace"
OUTPUT="/output"
cd "$WORKSPACE"

green()  { printf '\033[32m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }



require_project_yaml() {
    if [[ ! -f "$WORKSPACE/project.yaml" ]]; then
        red "Error: project.yaml not found."
        echo "Run 'make setup CLIENT=\"Your Client Name\" PROJECT=\"OCP-V\"' first."
        exit 1
    fi
}

validate_hld_generated_placeholders() {
    local md_dir="$WORKSPACE/HLD/markdown_files"
    [[ -d "$md_dir" ]] || return 0

    local files=()
    declare -A seen=()
    local candidates=(
        "$md_dir"/Drawio_*.md
        "$md_dir"/*_combined.md
        "$md_dir"/*_HLD_DecisionJourney_*.md
    )

    for file in "${candidates[@]}"; do
        [[ -f "$file" ]] || continue
        local base
        base="$(basename "$file")"
        case "$base" in
            Template_*|Drawio_Template_*)
                continue
                ;;
        esac
        if [[ -z "${seen[$file]:-}" ]]; then
            files+=("$file")
            seen["$file"]=1
        fi
    done

    if [[ ${#files[@]} -eq 0 ]]; then
        yellow "No generated HLD markdown files found for placeholder validation."
        return 0
    fi

    python3 "$WORKSPACE/scripts/lib/validate_placeholders.py" \
        --context "generated HLD output" \
        "${files[@]}"
}

# Collect generated artifacts into /output (if mounted)
collect_outputs() {
    [[ -d "$OUTPUT" ]] || return 0

    bold "Collecting outputs to output/..."

    move_or_copy() {
        local src="$1"
        local dst="$2"
        mkdir -p "$(dirname "$dst")"
        mv "$src" "$dst" 2>/dev/null || { cp "$src" "$dst" && rm -f "$src"; }
    }

    # PDFs
    if ls "$WORKSPACE"/HLD/PDFs/*.pdf &>/dev/null; then
        mkdir -p "$OUTPUT/HLD/PDFs"
        mv "$WORKSPACE"/HLD/PDFs/*.pdf "$OUTPUT/HLD/PDFs/"
    fi
    if ls "$WORKSPACE"/LLD/PDFs/*.pdf &>/dev/null; then
        mkdir -p "$OUTPUT/LLD/PDFs"
        mv "$WORKSPACE"/LLD/PDFs/*.pdf "$OUTPUT/LLD/PDFs/"
    fi

    # Combined / stitched markdown
    for f in "$WORKSPACE"/HLD/markdown_files/*_combined.md; do
        [[ -f "$f" ]] || continue
        move_or_copy "$f" "$OUTPUT/HLD/markdown_files/$(basename "$f")"
    done
    for f in "$WORKSPACE"/HLD/markdown_files/Drawio_*.md; do
        [[ -f "$f" ]] || continue
        move_or_copy "$f" "$OUTPUT/HLD/markdown_files/$(basename "$f")"
    done
    for f in "$WORKSPACE"/LLD/*_Combined.md; do
        [[ -f "$f" ]] || continue
        move_or_copy "$f" "$OUTPUT/LLD/$(basename "$f")"
    done
    for f in "$WORKSPACE"/LLD/Drawio_*.md; do
        [[ -f "$f" ]] || continue
        move_or_copy "$f" "$OUTPUT/LLD/$(basename "$f")"
    done

    # Diagram PNGs
    for dir in "$WORKSPACE"/Diagrams/phase*/; do
        [[ -d "$dir" ]] || continue
        local phase
        phase="$(basename "$dir")"
        if ls "$dir"/*.png &>/dev/null; then
            mkdir -p "$OUTPUT/Diagrams/$phase"
            cp "$dir"/*.png "$OUTPUT/Diagrams/$phase/"
        fi
    done
    if [[ -d "$WORKSPACE/LLD/diagrams" ]]; then
        cp -r "$WORKSPACE/LLD/diagrams" "$OUTPUT/LLD/" 2>/dev/null || true
    fi
    if [[ -d "$WORKSPACE/HLD/diagrams" ]]; then
        cp -r "$WORKSPACE/HLD/diagrams" "$OUTPUT/HLD/" 2>/dev/null || true
    fi

    # READOUT assets
    if [[ -d "$WORKSPACE/HLD/READOUT/assets" ]] && ls "$WORKSPACE"/HLD/READOUT/assets/*.png &>/dev/null; then
        mkdir -p "$OUTPUT/HLD/READOUT/assets"
        cp "$WORKSPACE"/HLD/READOUT/assets/*.png "$OUTPUT/HLD/READOUT/assets/"
    fi

    # Work items
    if [[ -d "$WORKSPACE/Work_Items" ]] && [[ "$(ls -A "$WORKSPACE/Work_Items" 2>/dev/null)" ]]; then
        cp -r "$WORKSPACE/Work_Items" "$OUTPUT/"
    fi

    # Clean transient artifacts from source tree
    rm -rf "$WORKSPACE"/HLD/PDFs "$WORKSPACE"/LLD/PDFs
    rm -rf "$WORKSPACE"/LLD/diagrams
    rm -rf "$WORKSPACE"/HLD/diagrams
    find "$WORKSPACE/Diagrams" -name "*.png" -delete 2>/dev/null || true
    rm -rf "$WORKSPACE"/HLD/READOUT/assets
    rm -rf "$WORKSPACE"/Work_Items

    green "Outputs written to output/"
}

SKIP_COLLECT=false

# ── Commands ─────────────────────────────────────────────────────────

cmd_setup() {
    local client="${1:-}"
    local project_code="${2:-OCP-V}"
    if [[ -z "$client" ]]; then
        red "Error: client name is required."
        echo "Usage: make setup CLIENT=\"Your Client Name\" PROJECT=\"OCP-V\""
        exit 1
    fi
    bold "=== Setting up project for: ${client} (${project_code}) ==="
    python3 "$WORKSPACE/scripts/setup_project.py" "$WORKSPACE" "$client" "$project_code"
    green "Setup complete."
}

cmd_build_hld() {
    require_project_yaml
    bold "=== Building HLD ==="
    echo ""

    bold "[1/6] Stitching phase files into combined HLD..."
    bash "$WORKSPACE/scripts/build/stitch_hld.sh"
    echo ""

    bold "[2/6] Exporting .drawio diagrams to PNG..."
    bash "$WORKSPACE/scripts/build/export_drawio.sh"
    echo ""

    bold "[3/6] Exporting mermaid diagrams to PNG..."
    bash "$WORKSPACE/scripts/build/export_mermaid.sh" --type hld
    echo ""

    bold "[4/6] Generating Drawio markdown variants..."
    python3 "$WORKSPACE/scripts/build/generate_drawio_variants.py" --type hld
    echo ""

    bold "[5/6] Generating HLD PDFs..."
    python3 "$WORKSPACE/scripts/build/generate_pdfs.py" --type hld --pdf-only
    echo ""

    bold "[6/6] Validating generated HLD placeholders..."
    validate_hld_generated_placeholders
    echo ""

    [[ "$SKIP_COLLECT" == true ]] || collect_outputs
    green "HLD build complete."
}

cmd_build_lld() {
    require_project_yaml
    bold "=== Building LLD ==="
    echo ""

    bold "[1/4] Stitching phase files into combined LLD..."
    bash "$WORKSPACE/scripts/build/stitch_lld.sh"
    echo ""

    bold "[2/4] Exporting mermaid diagrams to PNG..."
    bash "$WORKSPACE/scripts/build/export_mermaid.sh" --type lld
    echo ""

    bold "[3/4] Generating Drawio markdown variants..."
    python3 "$WORKSPACE/scripts/build/generate_drawio_variants.py" --type lld
    echo ""

    bold "[4/4] Generating LLD PDFs..."
    python3 "$WORKSPACE/scripts/build/generate_pdfs.py" --type lld --pdf-only
    echo ""

    [[ "$SKIP_COLLECT" == true ]] || collect_outputs
    green "LLD build complete."
}

cmd_build_all() {
    require_project_yaml
    bold "=== Full pipeline build ==="
    echo ""

    SKIP_COLLECT=true
    cmd_build_hld
    echo ""
    cmd_build_lld
    echo ""

    bold "=== Generating work items ==="
    python3 "$WORKSPACE/scripts/tools/lld_to_workitems.py" --format both --output-dir "$OUTPUT/Work_Items"
    echo ""

    SKIP_COLLECT=false
    collect_outputs
    green "Full build complete."
}

cmd_diagrams() {
    require_project_yaml
    bold "=== Exporting all diagrams ==="
    echo ""

    bold "HLD diagrams (.drawio -> PNG)..."
    bash "$WORKSPACE/scripts/build/export_drawio.sh"
    echo ""

    bold "HLD diagrams (mermaid -> PNG)..."
    bash "$WORKSPACE/scripts/build/export_mermaid.sh" --type hld
    echo ""

    bold "LLD diagrams (mermaid -> PNG)..."
    bash "$WORKSPACE/scripts/build/export_mermaid.sh" --type lld
    echo ""

    collect_outputs
    green "Diagram export complete."
}

cmd_pdfs() {
    require_project_yaml
    bold "=== Regenerating PDFs (no diagram re-export) ==="
    echo ""

    bold "HLD PDFs..."
    python3 "$WORKSPACE/scripts/build/generate_drawio_variants.py" --type hld
    python3 "$WORKSPACE/scripts/build/generate_pdfs.py" --type hld --pdf-only
    echo ""

    bold "LLD PDFs..."
    python3 "$WORKSPACE/scripts/build/generate_drawio_variants.py" --type lld
    python3 "$WORKSPACE/scripts/build/generate_pdfs.py" --type lld --pdf-only
    echo ""

    collect_outputs
    green "PDF generation complete."
}

cmd_workitems() {
    require_project_yaml
    bold "=== Generating work items from LLD ==="
    python3 "$WORKSPACE/scripts/tools/lld_to_workitems.py" --format both --output-dir "$OUTPUT/Work_Items"
    collect_outputs
    green "Work items written to output/Work_Items/"
}

cmd_rvtools() {
    require_project_yaml
    local shift_args=("${@}")
    if [[ ${#shift_args[@]} -eq 0 ]]; then
        red "Error: provide RVTools .xlsx file path(s)."
        echo "Usage: make rvtools FILES=\"RVTools/*.xlsx\""
        exit 1
    fi
    bold "=== Processing RVTools exports ==="
    local has_output=false
    for arg in "${shift_args[@]}"; do
        if [[ "$arg" == "-o" || "$arg" == "--output" ]]; then
            has_output=true
            break
        fi
    done
    if [[ "$has_output" == true ]]; then
        python3 "$WORKSPACE/scripts/tools/rvtools_to_schedule.py" "${shift_args[@]}"
    else
        python3 "$WORKSPACE/scripts/tools/rvtools_to_schedule.py" "${shift_args[@]}" -o "$OUTPUT/Migration_Weekly_Schedule.xlsx"
    fi
    collect_outputs
    green "Migration schedule generated."
}

cmd_status() {
    python3 "$WORKSPACE/scripts/setup_project.py" "$WORKSPACE" --status
}

cmd_help() {
    bold "Arch Design Doc Generator (container)"
    echo ""
    echo "  setup <client>    First-time project setup"
    echo "  build hld         Stitch + export diagrams + PDFs for HLD"
    echo "  build lld         Stitch + export diagrams + PDFs for LLD"
    echo "  build all         Full pipeline: HLD + LLD + work items"
    echo "  diagrams          Export all diagrams (.drawio + mermaid) to PNG"
    echo "  pdfs              Regenerate PDFs only (skip diagram export)"
    echo "  workitems         Create sprint work items from LLD"
    echo "  rvtools <files>   Process RVTools XLSX into migration schedule"
    echo "  status            Show project health and readiness"
    echo "  help              Show this message"
    echo ""
    echo "Normally invoked via the Makefile: make setup CLIENT=\"Example Client\" PROJECT=\"OCP-V\""
}

# ── Router ───────────────────────────────────────────────────────────

case "${1:-help}" in
    setup)      shift; cmd_setup "$@" ;;
    build)
        case "${2:-}" in
            hld) cmd_build_hld ;;
            lld) cmd_build_lld ;;
            all) cmd_build_all ;;
            *)   red "Unknown build target: ${2:-}"; echo "Use: build hld | build lld | build all"; exit 1 ;;
        esac
        ;;
    diagrams)   cmd_diagrams ;;
    pdfs)       cmd_pdfs ;;
    workitems)  cmd_workitems ;;
    rvtools)    shift; cmd_rvtools "$@" ;;
    status)     cmd_status ;;
    help|--help|-h) cmd_help ;;
    *)          red "Unknown command: $1"; cmd_help; exit 1 ;;
esac
