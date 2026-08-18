#!/usr/bin/env bash
#
# build_helpers.sh — Shared markdown/build helpers for shell build scripts.
#

set -euo pipefail

slugify() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g' | cut -c1-60
}

phase_tag_from_basename() {
    local base="$1"
    local base_lower
    base_lower="$(echo "$base" | tr '[:upper:]' '[:lower:]')"
    case "$base_lower" in
        *phase1*) echo "phase1" ;;
        *phase2*) echo "phase2" ;;
        *phase3*) echo "phase3" ;;
        *phase4*) echo "phase4" ;;
        *combined*) echo "combined" ;;
        *) echo "misc" ;;
    esac
}

extract_markdown_heading() {
    local line="$1"
    if [[ "$line" =~ ^#{1,6}[[:space:]]+(.+) ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}
