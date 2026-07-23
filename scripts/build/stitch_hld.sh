#!/usr/bin/env bash
#
# Regenerates the *_combined.md files from their phase source files
# using stitchmd. Run from anywhere — the script resolves its own paths.
#
# Usage:
#   ./stitch_hld.sh              # regenerate all combined docs
#   ./stitch_hld.sh <name>       # regenerate one (key from hld.summary_map in config)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"

MD_DIR="${PROJECT_ROOT}/HLD/markdown_files"
STITCHMD="${STITCHMD:-stitchmd}"

if ! command -v "$STITCHMD" &>/dev/null; then
    STITCHMD="${HOME}/go/bin/stitchmd"
    if [[ ! -x "$STITCHMD" ]]; then
        echo "Error: stitchmd not found. Install with: go install go.abhg.dev/stitchmd@latest" >&2
        exit 1
    fi
fi

declare -A SUMMARY_MAP
while IFS= read -r name; do
    summary=$(cfg_get "hld.summary_map.${name}.summary")
    output=$(cfg_get "hld.summary_map.${name}.output")
    SUMMARY_MAP["$name"]="${summary}|${output}"
done < <(python3 "${PROJECT_ROOT}/scripts/lib/config.py" --config "${PROJECT_ROOT}/project.yaml" get-map "hld.summary_map" | python3 -c "import sys,json; [print(k) for k in json.load(sys.stdin).keys()]")

stitch_one() {
    local name="$1"
    local entry="${SUMMARY_MAP[$name]}"
    local summary="${entry%%|*}"
    local output="${entry##*|}"

    if [[ ! -f "${MD_DIR}/${summary}" ]]; then
        echo "  Skipping ${name} — ${summary} not found"
        return
    fi

    echo "  ${summary} → ${output}"
    "$STITCHMD" -no-toc -o "${MD_DIR}/${output}" "${MD_DIR}/${summary}"
}

cd "$PROJECT_ROOT"

if [[ $# -ge 1 ]]; then
    for name in "$@"; do
        if [[ -z "${SUMMARY_MAP[$name]+x}" ]]; then
            echo "Error: unknown target '${name}'. Valid: ${!SUMMARY_MAP[*]}" >&2
            exit 1
        fi
        stitch_one "$name"
    done
else
    echo "=== Regenerating combined documents ==="
    for name in "${!SUMMARY_MAP[@]}"; do
        stitch_one "$name"
    done
fi

echo "Done."
