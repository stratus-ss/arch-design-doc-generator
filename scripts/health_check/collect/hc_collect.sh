#!/usr/bin/env bash
# hc_collect.sh — Health Check Data Collection Driver
#
# Runs all category collection scripts in sequence and produces a manifest.
#
# Usage:
#   bash hc_collect.sh [--kubeconfig PATH] [--output-dir PATH] [--categories 03,04,05]
#
# Environment variables (alternative to flags):
#   KUBECONFIG      Path to kubeconfig
#   HC_RESULTS_DIR  Output directory (overridden by --output-dir)
#
# Examples:
#   bash hc_collect.sh --kubeconfig ~/.kube/config --output-dir ./hc_results
#   KUBECONFIG=/path/to/kubeconfig bash hc_collect.sh
#
# All commands are read-only. No cluster state is modified.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

OUTPUT_DIR="${HC_RESULTS_DIR:-./hc_results}"
KUBECONFIG_PATH="${KUBECONFIG:-}"
RUN_CATEGORIES=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --kubeconfig) KUBECONFIG_PATH="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --categories) RUN_CATEGORIES="$2"; shift 2 ;;
        *) hc_warn "Unknown argument: $1"; shift ;;
    esac
done

export HC_RESULTS_DIR="$OUTPUT_DIR"
if [[ -n "$KUBECONFIG_PATH" ]]; then
    export HC_KUBECONFIG="$KUBECONFIG_PATH"
    export KUBECONFIG="$KUBECONFIG_PATH"
fi

mkdir -p "$HC_RESULTS_DIR"

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

hc_info "=== Health Check Collection Starting ==="
hc_info "Output directory: ${HC_RESULTS_DIR}"

if ! command -v oc &>/dev/null; then
    hc_error "oc CLI not found in PATH. Install the OpenShift CLI and retry."
    exit 1
fi

if ! oc cluster-info &>/dev/null; then
    hc_error "Cannot reach cluster API. Verify KUBECONFIG and network access."
    exit 1
fi

CLUSTER_SERVER="$(oc cluster-info 2>/dev/null | grep 'Kubernetes control plane' | awk '{print $NF}' || echo 'unknown')"
hc_info "Connected to: ${CLUSTER_SERVER}"

# ---------------------------------------------------------------------------
# Category script list
# ---------------------------------------------------------------------------

declare -a ALL_SCRIPTS=(
    "03_base_platform.sh"
    "04_topology.sh"
    "05_components.sh"
    "06_layered.sh"
    "07_cluster_health.sh"
    "08_day2.sh"
    "09_security.sh"
    "10_metrics.sh"
    "11_hardware.sh"
    "12_ccx.sh"
)

# Filter to requested categories if --categories was provided
declare -a SCRIPTS_TO_RUN=()
if [[ -n "$RUN_CATEGORIES" ]]; then
    IFS=',' read -ra REQUESTED <<< "$RUN_CATEGORIES"
    for script in "${ALL_SCRIPTS[@]}"; do
        prefix="${script%%_*}"
        for requested_prefix in "${REQUESTED[@]}"; do
            if [[ "$prefix" == "$requested_prefix" ]]; then
                SCRIPTS_TO_RUN+=("$script")
                break
            fi
        done
    done
else
    SCRIPTS_TO_RUN=("${ALL_SCRIPTS[@]}")
fi

# ---------------------------------------------------------------------------
# Run each category script
# ---------------------------------------------------------------------------

TOTAL_ERRORS=0
TOTAL_FILES=0
declare -a CATEGORIES_RUN=()

for script in "${SCRIPTS_TO_RUN[@]}"; do
    script_path="${SCRIPT_DIR}/${script}"
    if [[ ! -f "$script_path" ]]; then
        hc_warn "Script not found, skipping: ${script_path}"
        continue
    fi

    category="${script%.sh}"
    hc_info "--- Running: ${script} ---"
    HC_ERRORS=0
    HC_COLLECTED=0

    bash "$script_path" || true

    category_files="$(find "${HC_RESULTS_DIR}/${category}" -name '*.json' ! -name '*.meta.json' 2>/dev/null | wc -l | tr -d ' ')"
    TOTAL_FILES=$((TOTAL_FILES + category_files))
    TOTAL_ERRORS=$((TOTAL_ERRORS + HC_ERRORS))
    CATEGORIES_RUN+=("$category")
done

# ---------------------------------------------------------------------------
# Generate manifest
# ---------------------------------------------------------------------------

hc_info "Generating manifest..."

# Build file list as JSON array without jq
MANIFEST_FILE="${HC_RESULTS_DIR}/manifest.json"
{
    printf '{\n'
    printf '  "timestamp": "%s",\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf '  "cluster_server": "%s",\n' "$CLUSTER_SERVER"
    printf '  "output_dir": "%s",\n' "$HC_RESULTS_DIR"
    printf '  "total_files": %d,\n' "$TOTAL_FILES"
    printf '  "total_errors": %d,\n' "$TOTAL_ERRORS"

    # Categories array
    printf '  "categories": ['
    is_first_category=1
    for category in "${CATEGORIES_RUN[@]}"; do
        [[ $is_first_category -eq 0 ]] && printf ', '
        printf '"%s"' "$category"
        is_first_category=0
    done
    printf '],\n'

    # Files array
    printf '  "files": ['
    is_first_file=1
    while IFS= read -r -d '' json_path; do
        relative_path="${json_path#"${HC_RESULTS_DIR}/"}"
        [[ $is_first_file -eq 0 ]] && printf ','
        printf '\n    "%s"' "$relative_path"
        is_first_file=0
    done < <(find "$HC_RESULTS_DIR" -name '*.json' ! -name 'manifest.json' ! -name '*.meta.json' -print0 | sort -z)
    printf '\n  ]\n'
    printf '}\n'
} > "$MANIFEST_FILE"

hc_info "=== Collection Complete ==="
hc_info "Files collected : ${TOTAL_FILES}"
hc_info "Errors          : ${TOTAL_ERRORS}"
hc_info "Manifest        : ${MANIFEST_FILE}"

[[ $TOTAL_ERRORS -gt 0 ]] && hc_warn "Some commands failed (see WARN lines above). Check permissions or resource availability."
exit 0
