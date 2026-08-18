#!/usr/bin/env bash
# package_release.sh — build a distributable zip containing only what's needed
# to run the `make` targets on a fresh host: no planning/meta docs, no build
# output, no scratch/junk files, no client-specific or secret data.
#
# Usage:
#   scripts/shared/tools/package_release.sh [OUTPUT_ZIP]
#
# OUTPUT_ZIP defaults to $PACKAGE_OUTPUT, or ~/temp/arch-design-doc-generator/
# arch-design-doc-generator.zip if unset.
#
# File selection:
#   - Everything git-tracked, plus untracked-but-not-gitignored files
#     (so in-progress work that isn't committed yet is still picked up).
#   - Minus a fixed list of planning/meta paths that are never required to
#     run make targets (agent_planning/, agent_planning/execution/, cursor_plans/, openspec/, tests/,
#     .buddy/, CODE_REVIEW.md, AGENTS.md, ruff.toml, pyproject.toml). docs/ IS
#     included (project reference docs, not planning/meta).
#   - Minus known scratch/junk dirs that sometimes accumulate in the repo
#     root but aren't part of the project (tmp/, google-cloud-sdk/, .ruff_cache/).
#   - Minus client-scaffolded files left over from `make setup` runs.
#     Repo-root ADR/ is gitignored (filled engagement ADRs). `make setup`
#     also drops client-named copies into output/HLD/markdown_files/ and
#     output/LLD/ (excluded via output/). templates/ADR/ holds ADR_template.md
#     / ADR_EXAMPLE.md / Agenda_template.md.
#   - .git/ and output/ are never included.
#
# Update EXCLUDE_PATTERNS / EXCLUDE_EXACT below if the project layout changes.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

OUTPUT_ZIP="${1:-${PACKAGE_OUTPUT:-$HOME/temp/arch-design-doc-generator/arch-design-doc-generator.zip}}"
ARCHIVE_NAME="$(basename "$REPO_ROOT")"

# Top-level path prefixes to drop entirely (planning/meta docs, scratch dirs, generated).
EXCLUDE_PATTERNS='^(tmp/|google-cloud-sdk/|agent_planning/|agent_planning/execution/|cursor_plans/|openspec/|\.ruff_cache/|\.pytest_cache/|tests/|\.buddy/|output/|output-|RVTools/|ADR/)'
# Exact-match files to drop (planning/meta docs, generated stubs, dev-only config).
EXCLUDE_EXACT='^(CODE_REVIEW\.md|AGENTS\.md|ruff\.toml|pyproject\.toml)$'
# Client runtime files that must never ship even if gitignore is incomplete.
EXCLUDE_CLIENT='(^|/)slot_map\.json$|(^|/)project\.yaml$'

# A file is a client scaffold copy if it's a .md file directly under
# templates/HLD/markdown_files or templates/LLD that somehow isn't a Template_*
# (defense in depth — client copies normally live under output/ which is
# excluded). "[^/]*" (not "*") keeps this from matching templates/LLD/examples.
is_client_scaffold() {
    local f="$1"
    case "$f" in
        templates/HLD/markdown_files/[^/]*.md)
            [[ "$(basename "$f")" != Template_* ]]
            ;;
        templates/LLD/[^/]*.md)
            [[ "$(basename "$f")" != Template_* ]]
            ;;
        *)
            return 1
            ;;
    esac
}

echo "Building file list..."
FILELIST="$(mktemp)"
STAGING="$(mktemp -d)"
trap 'rm -rf "$FILELIST" "$STAGING"' EXIT

{
    git ls-files -z
    git ls-files -z --others --exclude-standard
} | tr '\0' '\n' | sort -u \
    | grep -v -E "$EXCLUDE_PATTERNS" \
    | grep -v -E "$EXCLUDE_EXACT" \
    | grep -v -E "$EXCLUDE_CLIENT" \
    | while IFS= read -r f; do
        [ -e "$f" ] || continue
        is_client_scaffold "$f" && continue
        printf '%s\n' "$f"
    done \
    > "$FILELIST"

file_count="$(wc -l < "$FILELIST")"
echo "  $file_count files selected"

echo "Staging..."
mkdir -p "$STAGING/$ARCHIVE_NAME"
rsync -a --files-from="$FILELIST" ./ "$STAGING/$ARCHIVE_NAME/"

echo "Sanity check for secrets / client-specific files..."
hits="$(find "$STAGING/$ARCHIVE_NAME" \( -iname 'project.yaml' -o -iname '*.env' -o -iname 'ADR_*.md' -o -iname '*credential*' -o -iname 'slot_map.json' -o -iname '*NFCU*' \) \
    ! -iname 'ADR_template.md' ! -iname 'ADR_EXAMPLE.md' 2>/dev/null || true)"
hits+="$(find "$STAGING/$ARCHIVE_NAME/templates/HLD/markdown_files" "$STAGING/$ARCHIVE_NAME/templates/LLD" -maxdepth 1 -iname '*.md' ! -iname 'Template_*' 2>/dev/null || true)"
if [ -n "$hits" ]; then
    echo "ERROR: found files that should never ship in the package:" >&2
    echo "$hits" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_ZIP")"
rm -f "$OUTPUT_ZIP"
( cd "$STAGING" && zip -rq -X "$OUTPUT_ZIP" "$ARCHIVE_NAME" )

size="$(du -h "$OUTPUT_ZIP" | cut -f1)"
echo "Done: $OUTPUT_ZIP ($size, $file_count files)"
