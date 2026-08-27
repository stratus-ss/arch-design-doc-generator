#!/usr/bin/env bash
# hc_collect_multi.sh — Multi-must-gather collection and merge orchestrator
#
# Automates the workflow of collecting health check data from multiple
# must-gather types within a single case download.
#
# Usage:
#   bash hc_collect_multi.sh --input ~/Downloads/must-gather.local.XYZ/
#   bash hc_collect_multi.sh --input ./case-bundle.tar.gz --tar
#
# Prerequisites:
#   - omc must be installed and in PATH
#   - python3 must be available (for hc_merge.py)
#
# The script will:
#   1. Discover must-gather subdirectories in the input
#   2. For each: omc use <subdir> then run hc_collect.sh
#   3. Merge results per cluster under a unified hc_results root
#
# Well-known OUTPUT_DIR and OUTPUT_DIR.tar.gz are this run only (cleared after
# cluster selection). Salvage copies live at OUTPUT_DIR.<cluster>.tar.gz.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
INPUT_PATH=""
OUTPUT_DIR="./hc_results"
PRODUCE_TAR=false
KEEP_INTERMEDIATES=false
CATEGORIES=""
CLUSTER_SELECT=""
WORKDIR=""
EXTRACTED_TEMP_DIR=""

cleanup_tempdirs() {
    if [[ "${KEEP_INTERMEDIATES:-false}" == true ]]; then
        if [[ -n "${WORKDIR:-}" && -d "${WORKDIR}" ]]; then
            log_info "Intermediate results kept at: ${WORKDIR}"
        fi
        if [[ -n "${EXTRACTED_TEMP_DIR:-}" && -d "${EXTRACTED_TEMP_DIR}" ]]; then
            log_info "Extracted tarball kept at: ${EXTRACTED_TEMP_DIR}"
        fi
        return 0
    fi

    [[ -n "${WORKDIR:-}" && -d "${WORKDIR}" ]] && rm -rf "${WORKDIR}"
    [[ -n "${EXTRACTED_TEMP_DIR:-}" && -d "${EXTRACTED_TEMP_DIR}" ]] && rm -rf "${EXTRACTED_TEMP_DIR}"
    return 0
}

trap cleanup_tempdirs EXIT

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_info()  { printf '[%s] [INFO ] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2; }
log_warn()  { printf '[%s] [WARN ] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2; }
log_error() { printf '[%s] [ERROR] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2; }

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/output_layout.sh"

sanitize_cluster_key() {
    local raw_name="$1"
    local sanitized="$raw_name"

    sanitized="${sanitized// /_}"
    sanitized="${sanitized//[^A-Za-z0-9._-]/_}"
    sanitized="${sanitized#_}"
    sanitized="${sanitized%_}"
    printf '%s' "${sanitized:-cluster}"
}

looks_like_cluster_bundle_name() {
    local name="$1"
    [[ "$name" =~ ^[0-9]{4}-(.+)-must-gather(\.tar\.gz)?$ ]]
}

resolve_cluster_bundle_dir() {
    local leaf_path="$1"
    local input_root="$2"
    local current="$leaf_path"

    while true; do
        local dir_name
        dir_name="$(basename "$current")"
        if looks_like_cluster_bundle_name "$dir_name"; then
            printf '%s' "$current"
            return 0
        fi
        if [[ "$current" == "$input_root" || "$current" == "/" ]]; then
            break
        fi
        current="$(dirname "$current")"
    done
    return 1
}

cluster_metadata_for_path() {
    local leaf_path="$1"
    local input_root="$2"
    local bundle_dir bundle_name cluster_name sequence

    bundle_dir="$(resolve_cluster_bundle_dir "$leaf_path" "$input_root")" || return 1
    bundle_name="$(basename "$bundle_dir")"
    [[ "$bundle_name" =~ ^([0-9]{4})-(.+)-must-gather(\.tar\.gz)?$ ]] || return 1

    sequence=$((10#${BASH_REMATCH[1]}))
    cluster_name="${BASH_REMATCH[2]}"
    cluster_name="${cluster_name#fixed_}"

    printf '%s\t%s\t%s\n' "$bundle_dir" "$sequence" "$(sanitize_cluster_key "$cluster_name")"
}

count_group_entries() {
    local group_text="$1"
    local count=0
    local line

    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        count=$((count + 1))
    done <<< "$group_text"

    printf '%s' "$count"
}

default_cluster_key() {
    local input_root="$1"
    sanitize_cluster_key "$(basename "$input_root")"
}

select_latest_group_paths() {
    local paths_nl="$1"
    local input_root="$2"
    local cluster_key="$3"
    local subdir metadata bundle_dir bundle_name sequence selected_bundle selected_sequence
    local -A bundle_paths=()
    local -A bundle_sequences=()

    while IFS= read -r subdir; do
        [[ -z "$subdir" ]] && continue
        metadata="$(cluster_metadata_for_path "$subdir" "$input_root" || true)"
        if [[ -z "$metadata" ]]; then
            continue
        fi

        IFS=$'\t' read -r bundle_dir sequence _ <<< "$metadata"
        bundle_name="$(basename "$bundle_dir")"
        bundle_paths["$bundle_name"]+="${subdir}"$'\n'
        bundle_sequences["$bundle_name"]="$sequence"
    done <<< "$paths_nl"

    if [[ ${#bundle_paths[@]} -le 1 ]]; then
        printf '%s' "$paths_nl"
        return 0
    fi

    selected_bundle=""
    selected_sequence=-1
    while IFS= read -r bundle_name; do
        [[ -z "$bundle_name" ]] && continue
        sequence="${bundle_sequences[$bundle_name]}"
        if (( sequence > selected_sequence )); then
            selected_sequence="$sequence"
            selected_bundle="$bundle_name"
        fi
    done < <(printf '%s\n' "${!bundle_sequences[@]}" | sort)

    log_warn "=================================================================="
    log_warn "Duplicate must-gather bundles detected for cluster: ${cluster_key}"
    while IFS= read -r bundle_name; do
        [[ -z "$bundle_name" ]] && continue
        if [[ "$bundle_name" == "$selected_bundle" ]]; then
            log_warn "  KEEP latest bundle : ${bundle_name}"
        else
            log_warn "  SKIP older bundle  : ${bundle_name}"
        fi
    done < <(printf '%s\n' "${!bundle_sequences[@]}" | sort)
    log_warn "Continuing with the latest bundle only."
    log_warn "=================================================================="

    printf '%s' "${bundle_paths[$selected_bundle]}"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --input)              INPUT_PATH="$2"; shift 2 ;;
        --output-dir)         OUTPUT_DIR="$2"; shift 2 ;;
        --tar)                PRODUCE_TAR=true; shift ;;
        --keep-intermediates|--keep-tempdirs) KEEP_INTERMEDIATES=true; shift ;;
        --categories)         CATEGORIES="$2"; shift 2 ;;
        --cluster)            CLUSTER_SELECT="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 --input <must-gather-dir-or-tarball> [--output-dir PATH] [--tar] [--keep-tempdirs] [--categories 03,04,05] [--cluster <name|all>]"
            echo "Well-known OUTPUT_DIR and OUTPUT_DIR.tar.gz are this run only; salvage is OUTPUT_DIR.<cluster>.tar.gz."
            exit 0
            ;;
        *) log_warn "Unknown argument: $1"; shift ;;
    esac
done

if [[ -z "$INPUT_PATH" ]]; then
    log_error "--input is required. Provide a must-gather.local directory or tarball."
    exit 1
fi

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
if ! command -v omc &>/dev/null; then
    log_error "omc not found in PATH."
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    log_error "python3 not found in PATH."
    exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/hc_collect.sh" ]]; then
    log_error "hc_collect.sh not found in ${SCRIPT_DIR}."
    exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/hc_merge.py" ]]; then
    log_error "hc_merge.py not found in ${SCRIPT_DIR}."
    exit 1
fi

# ---------------------------------------------------------------------------
# Resolve input to a directory
# ---------------------------------------------------------------------------
if [[ -f "$INPUT_PATH" ]] && [[ "$INPUT_PATH" == *.tar.gz || "$INPUT_PATH" == *.tgz ]]; then
    log_info "Extracting tarball: ${INPUT_PATH}"
    EXTRACTED_TEMP_DIR="$(mktemp -d -t hc_extract_XXXX)"
    tar -xzf "$INPUT_PATH" -C "$EXTRACTED_TEMP_DIR"
    # Find the must-gather.local* directory inside
    MG_DIR="$(find "$EXTRACTED_TEMP_DIR" -maxdepth 2 -type d -name 'must-gather.local*' | head -1)"
    if [[ -z "$MG_DIR" ]]; then
        # Maybe the tarball itself is the content
        MG_DIR="$EXTRACTED_TEMP_DIR"
    fi
elif [[ -d "$INPUT_PATH" ]]; then
    MG_DIR="$INPUT_PATH"
else
    log_error "Input path does not exist or is not a directory/tarball: ${INPUT_PATH}"
    exit 1
fi

log_info "Must-gather source: ${MG_DIR}"

# ---------------------------------------------------------------------------
# Discover must-gather subdirectories
#
# Case bundles nest to varying, unpredictable depths depending on how many
# must-gather types were collected and how the case-extraction tool laid
# them out, e.g.:
#   A) Single must-gather.local dir with N type subdirs inside:
#        must-gather.local.XYZ/
#          quay-io-openshift-release-dev-...
#          quay-io-pg-next-...
#          registry-redhat-io-cnv-...
#
#   B) Case-level directory with multiple must-gather dirs (sibling layout),
#      itself often one or more levels below the case directory:
#        0020-must-gather-YYYYMMDD.tar.gz/
#          must-gather-01/quay-io-openshift-release-dev-.../
#          must-gather-02/quay-io-pg-next-.../
#          must-gather.local.XYZ/registry-redhat-io-cnv-.../
#
# find_must_gather_dirs() therefore recurses to arbitrary depth (capped at
# MAX_MG_SEARCH_DEPTH as a safety bound), stopping as soon as it finds a
# directory that IS must-gather content (so it never descends into or past
# an already-matched leaf). This means --input can point at the top-level
# case directory directly — the caller does not need to already know the
# inner dirname.
#
# Case directories are frequently symlinks (e.g. `~/<case>` -> `/cases/<case>`,
# as created by `yank`). GNU find's default (physical) mode does NOT descend
# into a symlink given as the search root or encountered during traversal —
# it silently returns zero entries. `find -L` is used throughout to follow
# these symlinks; without it, discovery fails with "No must-gather
# directories found" even though the target directory has real content.
# ---------------------------------------------------------------------------
declare -a MG_SUBDIRS=()
MAX_MG_SEARCH_DEPTH=6

is_must_gather_dir() {
    local directory="$1"
    [[ -d "$directory/cluster-scoped-resources" ]] || [[ -d "$directory/namespaces" ]] || \
    [[ -d "$directory/nodes" ]] || [[ -d "$directory/monitoring" ]]
}

find_must_gather_dirs() {
    local search_dir="$1"
    local depth="${2:-0}"

    if [[ "$depth" -gt "$MAX_MG_SEARCH_DEPTH" ]]; then
        log_warn "Max search depth (${MAX_MG_SEARCH_DEPTH}) reached under ${search_dir}; stopping descent."
        return
    fi

    while IFS= read -r -d '' candidate; do
        local name
        name="$(basename "$candidate")"
        [[ "$name" == "." || "$name" == ".." ]] && continue

        if is_must_gather_dir "$candidate"; then
            MG_SUBDIRS+=("$candidate")
            continue
        fi

        find_must_gather_dirs "$candidate" "$((depth + 1))"
    done < <(find -L "$search_dir" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
}

if is_must_gather_dir "$MG_DIR"; then
    MG_SUBDIRS+=("$MG_DIR")
else
    find_must_gather_dirs "$MG_DIR"
fi

if [[ ${#MG_SUBDIRS[@]} -eq 0 ]]; then
    log_error "No must-gather directories found in ${MG_DIR}."
    log_error "Expected directories containing cluster-scoped-resources/, namespaces/, etc."
    exit 1
fi

log_info "Found ${#MG_SUBDIRS[@]} must-gather type(s):"
for subdir in "${MG_SUBDIRS[@]}"; do
    log_info "  - $(basename "$subdir")"
done

# ---------------------------------------------------------------------------
# Group discovered must-gathers by cluster
# ---------------------------------------------------------------------------
declare -A CLUSTER_GROUPS=()
declare -a UNGROUPED_DIRS=()
declare -a ALL_CLUSTERS=()

for subdir in "${MG_SUBDIRS[@]}"; do
    metadata="$(cluster_metadata_for_path "$subdir" "$MG_DIR" || true)"
    if [[ -z "$metadata" ]]; then
        UNGROUPED_DIRS+=("$subdir")
        continue
    fi

    IFS=$'\t' read -r _ _ cluster_key <<< "$metadata"
    CLUSTER_GROUPS["$cluster_key"]+="${subdir}"$'\n'
done

if [[ ${#UNGROUPED_DIRS[@]} -gt 0 ]]; then
    fallback_cluster="$(default_cluster_key "$MG_DIR")"
    if [[ -n "${CLUSTER_GROUPS[$fallback_cluster]+x}" ]]; then
        fallback_cluster="${fallback_cluster}_ungrouped"
    fi

    log_warn "Some must-gather directories did not map to a cluster-named bundle."
    log_warn "Grouping them under fallback key: ${fallback_cluster}"
    for subdir in "${UNGROUPED_DIRS[@]}"; do
        CLUSTER_GROUPS["$fallback_cluster"]+="${subdir}"$'\n'
    done
fi

if [[ ${#CLUSTER_GROUPS[@]} -eq 0 ]]; then
    log_error "No cluster groups could be derived from discovered must-gather directories."
    exit 1
fi

for cluster_key in "${!CLUSTER_GROUPS[@]}"; do
    CLUSTER_GROUPS["$cluster_key"]="$(select_latest_group_paths "${CLUSTER_GROUPS[$cluster_key]}" "$MG_DIR" "$cluster_key")"
done

mapfile -t ALL_CLUSTERS < <(printf '%s\n' "${!CLUSTER_GROUPS[@]}" | sort)

log_info "Detected ${#ALL_CLUSTERS[@]} cluster group(s):"
for cluster_key in "${ALL_CLUSTERS[@]}"; do
    log_info "  - ${cluster_key} ($(count_group_entries "${CLUSTER_GROUPS[$cluster_key]}") must-gather type(s))"
done

if [[ ! -t 0 && -z "$CLUSTER_SELECT" && ${#ALL_CLUSTERS[@]} -gt 1 ]]; then
    CLUSTER_SELECT="all"
    log_warn "Non-interactive mode detected with multiple clusters; processing all clusters."
fi

declare -a SELECTED_CLUSTERS=()
if [[ ${#ALL_CLUSTERS[@]} -eq 1 ]]; then
    SELECTED_CLUSTERS=("${ALL_CLUSTERS[@]}")
elif [[ -n "$CLUSTER_SELECT" ]]; then
    if [[ "$CLUSTER_SELECT" == "all" ]]; then
        SELECTED_CLUSTERS=("${ALL_CLUSTERS[@]}")
    elif [[ -n "${CLUSTER_GROUPS[$CLUSTER_SELECT]+x}" ]]; then
        SELECTED_CLUSTERS=("$CLUSTER_SELECT")
    else
        log_error "Cluster '${CLUSTER_SELECT}' not found. Available: ${ALL_CLUSTERS[*]}"
        exit 1
    fi
else
    log_info "=================================================================="
    log_info "Multiple clusters detected. Choose which cluster to process:"
    prompt_index=1
    for cluster_key in "${ALL_CLUSTERS[@]}"; do
        log_info "  ${prompt_index}) ${cluster_key} ($(count_group_entries "${CLUSTER_GROUPS[$cluster_key]}") must-gather type(s))"
        prompt_index=$((prompt_index + 1))
    done
    log_info "  ${prompt_index}) all"
    log_info "=================================================================="

    read -r -p "Select cluster(s) to process [1-${prompt_index}]: " selection
    if [[ "$selection" == "$prompt_index" ]]; then
        SELECTED_CLUSTERS=("${ALL_CLUSTERS[@]}")
    elif [[ "$selection" =~ ^[0-9]+$ ]] && (( selection >= 1 && selection < prompt_index )); then
        SELECTED_CLUSTERS=("${ALL_CLUSTERS[$((selection - 1))]}")
    else
        log_error "Invalid selection: ${selection}"
        exit 1
    fi
fi

log_info "Processing cluster(s): ${SELECTED_CLUSTERS[*]}"

clear_well_known_results "$OUTPUT_DIR" || exit 1

# ---------------------------------------------------------------------------
# Create working directory for intermediate results
# ---------------------------------------------------------------------------
WORKDIR="$(mktemp -d -t hc_multi_XXXX)"
log_info "Working directory: ${WORKDIR}"
mkdir -p "$OUTPUT_DIR"

# ---------------------------------------------------------------------------
# Collect and merge per cluster
# ---------------------------------------------------------------------------
declare -a PRODUCED_DIRS=()

for cluster_key in "${SELECTED_CLUSTERS[@]}"; do
    declare -a CLUSTER_MG_DIRS=()
    declare -a RUN_DIRS=()
    cluster_output="${OUTPUT_DIR}/${cluster_key}"
    RUN_COUNT=0

    while IFS= read -r subdir; do
        [[ -z "$subdir" ]] && continue
        CLUSTER_MG_DIRS+=("$subdir")
    done <<< "${CLUSTER_GROUPS[$cluster_key]}"

    log_info "=================================================================="
    log_info "Cluster: ${cluster_key}"
    log_info "Output : ${cluster_output}"
    log_info "=================================================================="

    for subdir in "${CLUSTER_MG_DIRS[@]}"; do
        RUN_COUNT=$((RUN_COUNT + 1))
        run_output="${WORKDIR}/${cluster_key}_run_${RUN_COUNT}"
        mg_name="$(basename "$subdir")"
        export HC_MG_SOURCE="$mg_name"

        log_info "--- [${RUN_COUNT}/${#CLUSTER_MG_DIRS[@]}] Collecting from: ${mg_name} ---"

        if ! omc use "$subdir" 2>&1; then
            log_warn "omc use failed for ${subdir}, skipping."
            continue
        fi

        COLLECT_ARGS=(--output-dir "$run_output")
        if [[ -n "$CATEGORIES" ]]; then
            COLLECT_ARGS+=(--categories "$CATEGORIES")
        fi

        if bash "${SCRIPT_DIR}/hc_collect.sh" "${COLLECT_ARGS[@]}"; then
            RUN_DIRS+=("$run_output")
            log_info "Collection complete → ${run_output}"
        else
            log_warn "hc_collect.sh returned non-zero for ${mg_name}, including partial results."
            if [[ -d "$run_output" ]]; then
                RUN_DIRS+=("$run_output")
            fi
        fi
    done

    if [[ ${#RUN_DIRS[@]} -eq 0 ]]; then
        log_warn "No successful collection runs for cluster ${cluster_key}. Skipping merge."
        continue
    fi

    log_info "Merging ${#RUN_DIRS[@]} result set(s) for cluster ${cluster_key}"
    MERGE_ARGS=("${RUN_DIRS[@]}" -o "$cluster_output")
    if [[ "$PRODUCE_TAR" == true ]]; then
        MERGE_ARGS+=(--tar)
    fi
    python3 "${SCRIPT_DIR}/hc_merge.py" "${MERGE_ARGS[@]}"

    PRODUCED_DIRS+=("$cluster_output")
    publish_cluster_salvage_tarball "$OUTPUT_DIR" "$cluster_key" \
        || log_warn "Salvage tarball publish failed for ${cluster_key} — continuing"
    CLUSTER_LEDGER="${cluster_output}/skipped_commands.jsonl"
    if [[ -f "$CLUSTER_LEDGER" ]]; then
        SKIP_TOTAL="$(wc -l < "$CLUSTER_LEDGER" | tr -d ' ')"
        log_info "Skip ledger: ${SKIP_TOTAL} entries → ${CLUSTER_LEDGER}"
    fi
    log_info "Reminder: place TSR HTML for cluster '${cluster_key}' in output/tsr_html/ before running hc-report."
    log_info "TSR auto-discovery matches by cluster UUID or cluster name from the HTML content."
done

if [[ ${#PRODUCED_DIRS[@]} -eq 0 ]]; then
    log_error "No successful collection runs completed for the selected clusters."
    exit 1
fi

if [[ "$PRODUCE_TAR" == true ]]; then
    tar -czf "${OUTPUT_DIR}.tar.gz" -C "$(dirname "$OUTPUT_DIR")" "$(basename "$OUTPUT_DIR")"
fi

log_info "=== Done ==="
log_info "Cluster outputs:"
for cluster_output in "${PRODUCED_DIRS[@]}"; do
    log_info "  - ${cluster_output}"
    if [[ "$PRODUCE_TAR" == true && -f "${cluster_output}.tar.gz" ]]; then
        log_info "    Per-cluster tarball: ${cluster_output}.tar.gz"
    fi
done
if [[ "$PRODUCE_TAR" == true ]]; then
    log_info "Aggregate tarball: ${OUTPUT_DIR}.tar.gz"
fi

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
