#!/usr/bin/env bash
# common.sh — Shared functions for all project scripts.
# Source this from any script. PROJECT_ROOT is always the repo root (parent of scripts/).

set -euo pipefail

# Resolve this file's location. lib/ lives under scripts/.
_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(dirname "$(dirname "$_COMMON_DIR")")}"
CONFIG_PY="${_COMMON_DIR}/config.py"
CONFIG_YAML="${PROJECT_ROOT}/project.yaml"

if [[ ! -f "$CONFIG_YAML" ]]; then
    echo "Error: project.yaml not found at $CONFIG_YAML" >&2
    exit 1
fi

cfg_get() { python3 "$CONFIG_PY" --config "$CONFIG_YAML" get "$1"; }
cfg_list() { python3 "$CONFIG_PY" --config "$CONFIG_YAML" get-list "$1"; }
cfg_css() { python3 "$CONFIG_PY" --config "$CONFIG_YAML" render-css --doc-type "$1"; }
