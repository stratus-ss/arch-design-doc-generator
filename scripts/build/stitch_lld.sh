#!/usr/bin/env bash
#
# Concatenates the phase LLD files into a single combined document.
#
# Usage:
#   ./stitch_lld.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"

LLD_DIR="${PROJECT_ROOT}/LLD"
COMBINED_FILE="$(cfg_get lld.combined_file)"
COMBINED_TITLE="$(cfg_get lld.combined_title)"
OUTPUT="${LLD_DIR}/${COMBINED_FILE}"

mapfile -t PHASE_FILES < <(cfg_list "phases[].lld_file")

echo "=== Generating combined LLD ==="

{
    cat <<HEADER
# ${COMBINED_TITLE}

> **Combined document** — all phase LLDs stitched into one file for review.

---

HEADER

    first=true
    for md in "${PHASE_FILES[@]}"; do
        src="${LLD_DIR}/${md}"
        if [[ ! -f "$src" ]]; then
            echo "  Skipping ${md} (not found)" >&2
            continue
        fi
        if [[ "$first" == true ]]; then
            first=false
        else
            printf '\n\n---\n\n'
        fi
        echo "  Including ${md}" >&2
        cat "$src"
    done
} > "$OUTPUT"

echo "  → $(basename "$OUTPUT") ($(du -h "$OUTPUT" | cut -f1))"
echo "Done."
