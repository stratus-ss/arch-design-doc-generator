#!/usr/bin/env bash
# Health Check Collection — Shared Library
# Source this file from each category script. Do not execute directly.
#
# Dependencies: oc CLI only. No jq, Python, or other tools required.

# Guard against double-sourcing
[[ -n "${_HC_COMMON_LOADED:-}" ]] && return 0
_HC_COMMON_LOADED=1

# ---------------------------------------------------------------------------
# Global state (set by hc_init or the driver)
# ---------------------------------------------------------------------------
HC_RESULTS_DIR="${HC_RESULTS_DIR:-}"
HC_KUBECONFIG="${HC_KUBECONFIG:-${KUBECONFIG:-}}"
export HC_CLI="${HC_CLI:-oc}"
HC_ERRORS=0
HC_COLLECTED=0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

hc_log() {
    local level="$1"; shift
    local msg="$*"
    local ts
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf '[%s] [%s] %s\n' "$ts" "$level" "$msg" >&2
}

hc_info()  { hc_log "INFO " "$@"; }
hc_warn()  { hc_log "WARN " "$@"; }
hc_error() { hc_log "ERROR" "$@"; HC_ERRORS=$((HC_ERRORS + 1)); }

# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

hc_json_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

hc_extract_chapter() {
    local script_path="$1"
    local header chapter
    header="$(sed -n '2p' "$script_path" 2>/dev/null || true)"
    chapter="$(printf '%s' "$header" | sed -n 's/.*Chapter[[:space:]]\([0-9.]\+\).*/\1/p')"
    printf '%s' "${chapter:-unknown}"
}

hc_write_capture_metadata() {
    local meta_out="$1"
    local command_str="$2"
    local script_path="$3"
    local category="$4"
    local check_name="$5"

    local timestamp script_name chapter
    local escaped_cmd escaped_script escaped_chapter escaped_category escaped_check

    timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    script_name="$(basename -- "$script_path")"
    chapter="$(hc_extract_chapter "$script_path")"

    escaped_cmd="$(hc_json_escape "$command_str")"
    escaped_script="$(hc_json_escape "$script_name")"
    escaped_chapter="$(hc_json_escape "$chapter")"
    escaped_category="$(hc_json_escape "$category")"
    escaped_check="$(hc_json_escape "$check_name")"

    if ! printf '{"command":"%s","script":"%s","chapter":"%s","category":"%s","check_name":"%s","timestamp":"%s"}\n' \
        "$escaped_cmd" "$escaped_script" "$escaped_chapter" "$escaped_category" "$escaped_check" "$timestamp" > "$meta_out"; then
        hc_warn "  metadata write failed: ${meta_out}"
    fi
}

# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

hc_init() {
    local category="${1:-unknown}"

    if [[ -z "$HC_RESULTS_DIR" ]]; then
        hc_error "HC_RESULTS_DIR is not set. Export it before sourcing common.sh or use hc_collect.sh."
        return 1
    fi

    mkdir -p "${HC_RESULTS_DIR}/${category}"

    # Verify oc is available
    if ! command -v oc &>/dev/null; then
        hc_error "oc CLI not found in PATH. Install the OpenShift CLI before running collection."
        return 1
    fi

    # Apply kubeconfig if set
    if [[ -n "$HC_KUBECONFIG" ]]; then
        export KUBECONFIG="$HC_KUBECONFIG"
    fi

    # Verify cluster connectivity
    if ! oc cluster-info &>/dev/null; then
        hc_error "Cannot reach cluster API. Check KUBECONFIG and network connectivity."
        return 1
    fi

    hc_info "Initialized category '${category}' → ${HC_RESULTS_DIR}/${category}/"
    return 0
}

# ---------------------------------------------------------------------------
# JSON capture helper
# Runs: oc <oc_args...> -o json
# Writes: $HC_RESULTS_DIR/$category/$name.json
# On oc failure: writes an error envelope JSON and continues (does not abort).
# ---------------------------------------------------------------------------

hc_capture_json() {
    local category="$1"
    local name="$2"
    shift 2
    local out="${HC_RESULTS_DIR}/${category}/${name}.json"
    local meta_out="${HC_RESULTS_DIR}/${category}/${name}.meta.json"
    local command_str="oc $* -o json"
    local script_path="${BASH_SOURCE[1]-}"
    if [[ -z "$script_path" ]]; then
        script_path="$0"
    fi
    local tmp
    tmp="$(mktemp)"

    hc_info "  collect: ${command_str} → ${category}/${name}.json"

    local exit_code=0
    local tmp_err
    tmp_err="$(mktemp)"
    oc "$@" -o json >"$tmp" 2>"$tmp_err" || exit_code=$?

    if [[ $exit_code -eq 0 && -s "$tmp" ]]; then
        # Treat a valid JSON response with an empty items array as NOT_FOUND (not installed)
        local item_count
        item_count="$(python3 -c "
import json, sys
try:
    d = json.load(open('$tmp'))
    items = d.get('items', None)
    if items is not None:
        print(len(items))
    else:
        print(1)
except Exception:
    print(1)
" 2>/dev/null || echo 1)"

        if [[ "$item_count" -eq 0 ]]; then
            printf '{"_hc_not_found": true, "command": "oc %s -o json", "exit_code": 0, "note": "resource exists but returned empty list", "timestamp": "%s"}\n' \
                "$*" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$out"
            hc_info "  not-found (empty list): oc $* -o json"
        else
            mv "$tmp" "$out"
            HC_COLLECTED=$((HC_COLLECTED + 1))
        fi
    else
        # Check if this is a CRD-not-found error (operator not installed) vs a real error
        local err_msg
        err_msg="$(cat "$tmp_err" 2>/dev/null)"
        if echo "$err_msg" | grep -q "the server doesn't have a resource type"; then
            printf '{"_hc_not_found": true, "command": "oc %s -o json", "exit_code": %d, "note": "CRD not present — operator not installed", "timestamp": "%s"}\n' \
                "$*" "$exit_code" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$out"
            hc_info "  not-installed (CRD missing): oc $* -o json"
        else
            # Write an error envelope so the report generator knows this was attempted
            printf '{"_hc_error": true, "command": "oc %s -o json", "exit_code": %d, "timestamp": "%s"}\n' \
                "$*" "$exit_code" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$out"
            hc_warn "  skipped (exit_code=${exit_code}): oc $* -o json"
            HC_ERRORS=$((HC_ERRORS + 1))
        fi
    fi
    hc_write_capture_metadata "$meta_out" "$command_str" "$script_path" "$category" "$name"
    rm -f "$tmp" "$tmp_err"
}

# ---------------------------------------------------------------------------
# Text/table capture helper
# Runs an arbitrary command, wraps output in a JSON envelope.
# Writes: $HC_RESULTS_DIR/$category/$name.json
# ---------------------------------------------------------------------------

hc_capture_text() {
    local category="$1"
    local name="$2"
    shift 2
    local out="${HC_RESULTS_DIR}/${category}/${name}.json"
    local meta_out="${HC_RESULTS_DIR}/${category}/${name}.meta.json"
    local command_str="$*"
    local script_path="${BASH_SOURCE[1]-}"
    if [[ -z "$script_path" ]]; then
        script_path="$0"
    fi
    local tmp_out tmp_err
    tmp_out="$(mktemp)"
    tmp_err="$(mktemp)"

    hc_info "  collect: ${command_str} → ${category}/${name}.json"

    local exit_code=0
    "$@" >"$tmp_out" 2>"$tmp_err" || exit_code=$?

    # Stream-escape output for JSON — never load into a variable or printf arg
    # to avoid ENOSPC on large must-gather data (ARG_MAX overflow)
    {
        printf '{"_hc_text": true, "command": "%s", "output": "' "$command_str"
        sed 's/\\/\\\\/g; s/"/\\"/g' "$tmp_out" | \
            awk '{printf "%s\\n", $0}' | \
            sed 's/\\n$//'
        printf '", "exit_code": %d, "timestamp": "%s"}\n' \
            "$exit_code" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    } > "$out"

    hc_write_capture_metadata "$meta_out" "$command_str" "$script_path" "$category" "$name"

    rm -f "$tmp_out" "$tmp_err"

    if [[ $exit_code -eq 0 ]]; then
        HC_COLLECTED=$((HC_COLLECTED + 1))
    else
        hc_warn "  command exited ${exit_code}: $*"
        HC_ERRORS=$((HC_ERRORS + 1))
    fi
}

# ---------------------------------------------------------------------------
# Category summary
# ---------------------------------------------------------------------------

hc_summary() {
    local category="$1"
    local file_count
    file_count="$(find "${HC_RESULTS_DIR}/${category}" -name '*.json' ! -name '*.meta.json' | wc -l | tr -d ' ')"
    hc_info "Category '${category}' complete: ${file_count} files, ${HC_ERRORS} error(s) this run."
}
