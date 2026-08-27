#!/usr/bin/env bash
# Well-known results layout helpers for hc_collect_multi.sh.
# Source this file. Do not execute directly.

set -euo pipefail

[[ -n "${_HC_OUTPUT_LAYOUT_LOADED:-}" ]] && return 0
_HC_OUTPUT_LAYOUT_LOADED=1

_layout_log_info() {
    if declare -F log_info >/dev/null 2>&1; then
        log_info "$@"
    else
        printf '[%s] [INFO ] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
    fi
}

_layout_log_error() {
    if declare -F log_error >/dev/null 2>&1; then
        log_error "$@"
    else
        printf '[%s] [ERROR] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
    fi
}

output_path_is_forbidden() {
    local output_dir="$1"

    if [[ -z "$output_dir" || "$output_dir" == "/" ]]; then
        return 0
    fi

    if command -v realpath >/dev/null 2>&1; then
        local resolved_output resolved_home
        resolved_output="$(realpath -m -- "$output_dir")"
        if [[ "$resolved_output" == "/" ]]; then
            return 0
        fi
        if [[ -n "${HOME:-}" ]]; then
            resolved_home="$(realpath -m -- "$HOME")"
            if [[ "$resolved_output" == "$resolved_home" ]]; then
                return 0
            fi
        fi
        return 1
    fi

    if [[ "$output_dir" == "/" || "$output_dir" == "${HOME:-}" || "$output_dir" == "${HOME:-}/" ]]; then
        return 0
    fi
    return 1
}

clear_well_known_results() {
    local output_dir="$1"
    local aggregate_tarball="${output_dir}.tar.gz"

    if output_path_is_forbidden "$output_dir"; then
        _layout_log_error "Refusing to clear well-known results at forbidden path: ${output_dir}"
        return 1
    fi

    if [[ -e "$output_dir" || -L "$output_dir" ]]; then
        _layout_log_info "Removing well-known results directory: ${output_dir}"
        rm -rf -- "$output_dir"
    fi
    if [[ -e "$aggregate_tarball" || -L "$aggregate_tarball" ]]; then
        _layout_log_info "Removing well-known aggregate tarball: ${aggregate_tarball}"
        rm -f -- "$aggregate_tarball"
    fi
    return 0
}

publish_cluster_salvage_tarball() {
    local output_dir="$1"
    local cluster_key="$2"
    local cluster_output="${output_dir}/${cluster_key}"
    local inner_tarball="${cluster_output}.tar.gz"
    local salvage_tarball="${output_dir}.${cluster_key}.tar.gz"

    if [[ -f "$inner_tarball" ]]; then
        cp -f -- "$inner_tarball" "$salvage_tarball"
    elif [[ -d "$cluster_output" ]]; then
        tar -czf "$salvage_tarball" -C "$(dirname "$cluster_output")" "$(basename "$cluster_output")"
    else
        _layout_log_error "Cannot publish salvage tarball: missing ${inner_tarball} and ${cluster_output}"
        return 1
    fi
    _layout_log_info "Salvage tarball: ${salvage_tarball}"
    return 0
}
