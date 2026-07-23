#!/usr/bin/env bash
#
# Exports .drawio files from Diagrams/ into PNG and syncs HLD READOUT assets.
#
# Usage:
#   ./export_drawio.sh            # export all
#   ./export_drawio.sh <file>     # export one file

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"

DIAGRAMS_ROOT="${PROJECT_ROOT}/$(cfg_get paths.diagrams)"
READOUT_ASSETS_DIR="${PROJECT_ROOT}/HLD/READOUT/assets"
SCALE=2

mapfile -t PHASE_DIRS < <(cfg_list "diagrams.phase_dirs")
mapfile -t TOP_LEVEL_DRAWIO_PATTERNS < <(cfg_list "diagrams.top_level_patterns")

export_file() {
    local src="$1"
    local base
    base="$(basename "$src")"
    local dir
    dir="$(dirname "$src")"
    local out="${dir}/${base}.png"

    echo "  ${base} → ${base}.png"
    drawio -x -f png -s "${SCALE}" -o "$out" "$src"
}

sync_readout_assets() {
    mkdir -p "${READOUT_ASSETS_DIR}"
    rm -f "${READOUT_ASSETS_DIR}"/*.png

    echo "Syncing READOUT assets..."

    for phase in "${PHASE_DIRS[@]}"; do
        local dir="${DIAGRAMS_ROOT}/${phase}"
        [[ -d "$dir" ]] || continue
        for png in "$dir"/*.png; do
            [[ -f "$png" ]] && cp "$png" "${READOUT_ASSETS_DIR}/" || true
        done
    done

    for pattern in "${TOP_LEVEL_DRAWIO_PATTERNS[@]}"; do
        local png_pattern="${pattern%.drawio}*.drawio.png"
        for png in "${DIAGRAMS_ROOT}"/${png_pattern}; do
            [[ -f "$png" ]] && cp "$png" "${READOUT_ASSETS_DIR}/" || true
        done
    done
}

if [[ $# -ge 1 ]]; then
    for f in "$@"; do
        if [[ ! -f "$f" ]]; then
            echo "Error: $f not found" >&2
            exit 1
        fi
        export_file "$f"
    done
    sync_readout_assets
else
    echo "Exporting top-level diagrams..."
    for pattern in "${TOP_LEVEL_DRAWIO_PATTERNS[@]}"; do
        for f in "${DIAGRAMS_ROOT}"/${pattern}; do
            [[ -f "$f" ]] && export_file "$f" || true
        done
    done

    for phase in "${PHASE_DIRS[@]}"; do
        dir="${DIAGRAMS_ROOT}/${phase}"
        [[ -d "$dir" ]] || continue
        echo "Exporting ${phase} diagrams..."
        for f in "$dir"/*.drawio; do
            [[ -f "$f" ]] && export_file "$f" || true
        done
    done

    sync_readout_assets
    echo "Done."
fi
