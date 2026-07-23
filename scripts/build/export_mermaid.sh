#!/usr/bin/env bash
#
# Unified mermaid exporter for HLD and LLD markdown sources.
#
# Usage:
#   ./export_mermaid.sh --type hld
#   ./export_mermaid.sh --type lld
#   ./export_mermaid.sh --type hld file.md [file2.md]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/build_helpers.sh"

DOC_TYPE=""
SCALE=2
PUPPETEER_CFG="/toolkit/puppeteer.json"
MMDC="${MMDC:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)
            DOC_TYPE="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

if [[ "$DOC_TYPE" != "hld" && "$DOC_TYPE" != "lld" ]]; then
    echo "Usage: $0 --type hld|lld [markdown_files...]" >&2
    exit 1
fi

if [[ -z "$MMDC" ]]; then
    if command -v mmdc &>/dev/null; then
        MMDC="mmdc"
    else
        MMDC="npx -y @mermaid-js/mermaid-cli"
    fi
fi

MMDC_PUPPET_ARGS=()
[[ -f "$PUPPETEER_CFG" ]] && MMDC_PUPPET_ARGS=(-p "$PUPPETEER_CFG")

PRIMARY_COLOR="$(cfg_get brand.primary_color)"
SECONDARY_COLOR="$(cfg_get brand.secondary_color)"
MMDC_LOG_DIR="${PROJECT_ROOT}/output/.logs"
MMDC_LOG_FILE="${MMDC_LOG_DIR}/export_mermaid.log"
mkdir -p "$MMDC_LOG_DIR"

MMDC_CONFIG=$(mktemp /tmp/mmdc-config-XXXX.json)
trap 'rm -f "$MMDC_CONFIG"' EXIT
cat > "$MMDC_CONFIG" <<JSON
{
  "theme": "default",
  "themeVariables": {
    "primaryColor": "${PRIMARY_COLOR}",
    "primaryTextColor": "#fff",
    "primaryBorderColor": "${SECONDARY_COLOR}",
    "lineColor": "${SECONDARY_COLOR}",
    "secondaryColor": "#f1f5f9",
    "tertiaryColor": "#e2e8f0"
  }
}
JSON

if [[ "$DOC_TYPE" == "hld" ]]; then
    MD_DIR="${PROJECT_ROOT}/HLD/markdown_files"
    DIAGRAMS_DIR="${PROJECT_ROOT}/HLD/diagrams"
    mapfile -t PHASE_FILES < <(cfg_list "hld.phase_files")
    mapfile -t COMBINED_FILES < <(cfg_list "hld.combined_files")
else
    MD_DIR="${PROJECT_ROOT}/LLD"
    DIAGRAMS_DIR="${PROJECT_ROOT}/LLD/diagrams"
    mapfile -t PHASE_FILES < <(cfg_list "phases[].lld_file")
    COMBINED_FILE="$(cfg_get lld.combined_file)"
fi

extract_and_render() {
    local src="$1"
    local basename_noext
    basename_noext="$(basename "${src%.md}")"
    local phase_tag
    phase_tag="$(phase_tag_from_basename "$basename_noext")"

    local outdir="${DIAGRAMS_DIR}/${phase_tag}"
    mkdir -p "$outdir"

    local count=0
    local in_mermaid=false
    local mermaid_buf=""
    local last_heading=""
    local diagram_idx=0

    while IFS= read -r line; do
        local heading
        if heading="$(extract_markdown_heading "$line")"; then
            last_heading="$heading"
        fi

        if [[ "$line" == '```mermaid' ]]; then
            in_mermaid=true
            mermaid_buf=""
            continue
        fi

        if [[ "$in_mermaid" == true ]]; then
            if [[ "$line" == '```' ]]; then
                in_mermaid=false
                diagram_idx=$((diagram_idx + 1))

                local slug
                if [[ -n "$last_heading" ]]; then
                    slug="$(slugify "$last_heading")"
                else
                    slug="diagram"
                fi
                local outname="${phase_tag}_${diagram_idx}_${slug}.png"
                local tmpfile
                tmpfile=$(mktemp /tmp/mermaid-XXXX.mmd)

                if echo "$mermaid_buf" | grep -qE '\{[A-Z_]+\}|\{TBD\}'; then
                    echo "  ${outname} (skipped: contains unresolved placeholders)"
                else
                    echo "$mermaid_buf" > "$tmpfile"
                    echo "  ${outname}"
                    $MMDC -i "$tmpfile" -o "${outdir}/${outname}" \
                        -s "$SCALE" -c "$MMDC_CONFIG" -b transparent \
                        "${MMDC_PUPPET_ARGS[@]}" \
                        2> >(tee -a "$MMDC_LOG_FILE" >&2) || echo "    ⚠ render failed for ${outname}" >&2
                fi
                rm -f "$tmpfile"
                count=$((count + 1))
            else
                mermaid_buf+="${line}"$'\n'
            fi
        fi
    done < "$src"

    echo "  ${basename_noext}: ${count} diagrams exported to ${phase_tag}/"
}

cd "$PROJECT_ROOT"

if [[ $# -ge 1 ]]; then
    for f in "$@"; do
        if [[ ! -f "$f" ]]; then
            echo "Error: $f not found" >&2
            exit 1
        fi
        extract_and_render "$f"
    done
    echo "Done."
    exit 0
fi

echo "=== Exporting mermaid diagrams from ${DOC_TYPE^^} files ==="
for md in "${PHASE_FILES[@]}"; do
    src="${MD_DIR}/${md}"
    [[ -f "$src" ]] || continue
    extract_and_render "$src"
done

if [[ "$DOC_TYPE" == "hld" ]]; then
    for md in "${COMBINED_FILES[@]}"; do
        src="${MD_DIR}/${md}"
        [[ -f "$src" ]] || continue
        extract_and_render "$src"
    done
else
    combined="${MD_DIR}/${COMBINED_FILE}"
    [[ -f "$combined" ]] && extract_and_render "$combined" || true
fi

echo "Done."
