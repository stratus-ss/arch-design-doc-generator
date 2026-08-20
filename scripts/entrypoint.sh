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

export PROJECT_ROOT="$WORKSPACE"
export PYTHONPATH="$WORKSPACE/scripts/shared/lib:/toolkit/shared/lib:${PYTHONPATH:-}"

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
    local md_dir="$WORKSPACE/output/HLD/markdown_files"
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

    python3 "/toolkit/shared/lib/validate_placeholders.py" \
        --context "generated HLD output" \
        "${files[@]}"
}

# Collect generated artifacts into /output (if mounted).
# Builds already write under $WORKSPACE/output, which is typically the same
# bind mount as /output. Sync only when the two paths differ.
collect_outputs() {
    [[ -d "$OUTPUT" ]] || return 0

    bold "Collecting outputs to output/..."

    local ws_out="$WORKSPACE/output"
    if [[ ! -d "$ws_out" ]]; then
        yellow "No workspace output/ directory to collect."
        return 0
    fi

    # /workspace/output and /output are often the same host dir bind-mounted twice.
    if [[ "$ws_out" -ef "$OUTPUT" ]]; then
        green "Outputs already under output/ (same mount as /output)."
        return 0
    fi

    mkdir -p "$OUTPUT"
    cp -a "$ws_out"/. "$OUTPUT"/
    green "Outputs synced to /output from workspace/output/"
}

SKIP_COLLECT=false

# ── Commands ─────────────────────────────────────────────────────────

cmd_setup() {
    local client="${1:-}"
    if [[ -z "$client" ]]; then
        red "Error: client name is required."
        echo "Usage: make setup CLIENT=\"Your Client Name\" PROJECT=\"OCP-V\" [FORCE=1]"
        exit 1
    fi
    shift
    local project_code="OCP-V"
    if [[ $# -gt 0 && "${1:-}" != --* ]]; then
        project_code="$1"
        shift
    fi
    if [[ "${SETUP_FORCE:-}" == "1" ]]; then
        set -- "$@" --force
    fi
    bold "=== Setting up project for: ${client} (${project_code}) ==="
    python3 "/toolkit/setup_project.py" "$WORKSPACE" "$client" "$project_code" "$@"
    green "Setup complete."
}

cmd_build_hld() {
    require_project_yaml
    bold "=== Building HLD ==="
    echo ""

    bold "[1/6] Stitching phase files into combined HLD..."
    bash "/toolkit/hld_lld/build/stitch_hld.sh"
    echo ""

    bold "[2/6] Exporting .drawio diagrams to PNG..."
    bash "/toolkit/hld_lld/build/export_drawio.sh"
    echo ""

    bold "[3/6] Exporting mermaid diagrams to PNG..."
    bash "/toolkit/hld_lld/build/export_mermaid.sh" --type hld
    echo ""

    bold "[4/6] Generating Drawio markdown variants..."
    python3 "/toolkit/hld_lld/build/generate_drawio_variants.py" --type hld
    echo ""

    bold "[5/6] Generating HLD PDFs..."
    python3 "/toolkit/hld_lld/build/generate_pdfs.py" --type hld --pdf-only
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
    bash "/toolkit/hld_lld/build/stitch_lld.sh"
    echo ""

    bold "[2/4] Exporting mermaid diagrams to PNG..."
    bash "/toolkit/hld_lld/build/export_mermaid.sh" --type lld
    echo ""

    bold "[3/4] Generating Drawio markdown variants..."
    python3 "/toolkit/hld_lld/build/generate_drawio_variants.py" --type lld
    echo ""

    bold "[4/4] Generating LLD PDFs..."
    python3 "/toolkit/hld_lld/build/generate_pdfs.py" --type lld --pdf-only
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
    python3 "/toolkit/hld_lld/lld_to_workitems.py" --format both --output-dir "$OUTPUT/Work_Items"
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
    bash "/toolkit/hld_lld/build/export_drawio.sh"
    echo ""

    bold "HLD diagrams (mermaid -> PNG)..."
    bash "/toolkit/hld_lld/build/export_mermaid.sh" --type hld
    echo ""

    bold "LLD diagrams (mermaid -> PNG)..."
    bash "/toolkit/hld_lld/build/export_mermaid.sh" --type lld
    echo ""

    collect_outputs
    green "Diagram export complete."
}

cmd_pdfs() {
    require_project_yaml
    bold "=== Regenerating PDFs (no diagram re-export) ==="
    echo ""

    bold "HLD PDFs..."
    python3 "/toolkit/hld_lld/build/generate_drawio_variants.py" --type hld
    python3 "/toolkit/hld_lld/build/generate_pdfs.py" --type hld --pdf-only
    echo ""

    bold "LLD PDFs..."
    python3 "/toolkit/hld_lld/build/generate_drawio_variants.py" --type lld
    python3 "/toolkit/hld_lld/build/generate_pdfs.py" --type lld --pdf-only
    echo ""

    collect_outputs
    green "PDF generation complete."
}

cmd_workitems() {
    require_project_yaml
    bold "=== Generating work items from LLD ==="
    python3 "/toolkit/hld_lld/lld_to_workitems.py" --format both --output-dir "$OUTPUT/Work_Items"
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
        python3 "/toolkit/rvtools/rvtools_to_schedule.py" "${shift_args[@]}"
    else
        python3 "/toolkit/rvtools/rvtools_to_schedule.py" "${shift_args[@]}" -o "$OUTPUT/Migration_Weekly_Schedule.xlsx"
    fi
    collect_outputs
    green "Migration schedule generated."
}

cmd_status() {
    python3 "/toolkit/setup_project.py" "$WORKSPACE" --status
}

cmd_hc_report() {
    bold "=== Generating Health Check Report ==="
    export PYTHONPATH="$WORKSPACE/scripts/health_check:$WORKSPACE/scripts/shared/lib:/toolkit/health_check:/toolkit/shared/lib:${PYTHONPATH:-}"
    python3 /toolkit/health_check/generate_report.py "$@"
    collect_outputs
    green "Health Check report complete."
}

cmd_hc_investigate() {
    bold "=== Investigating Health Check finding ==="
    export PYTHONPATH="$WORKSPACE/scripts/health_check:$WORKSPACE/scripts/shared/lib:/toolkit/health_check:/toolkit/shared/lib:${PYTHONPATH:-}"
    python3 /toolkit/health_check/hc_investigate.py "$@"
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
    echo "  hc-report         Generate Health Check report from collected data"
    echo "  hc-investigate    Trace a Health Check finding to raw evidence"
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
    hc-report)  shift; cmd_hc_report "$@" ;;
    hc-investigate) shift; cmd_hc_investigate "$@" ;;
    status)     cmd_status ;;
    help|--help|-h) cmd_help ;;
    *)          red "Unknown command: $1"; cmd_help; exit 1 ;;
esac
