#!/usr/bin/env bash
# hc_fetch_results.sh — Fetch collected HC results from a remote support shell server.
#
# Prefers a pre-built tarball (produced by hc_collect_multi.sh --tar) over a raw
# rsync of the results directory, since a single-file transfer is faster and
# gives a clean, atomic snapshot. Falls back to a raw directory sync when no
# tarball is present on the remote host.
#
# Usage:
#   bash hc_fetch_results.sh --ssh-host user@host --remote-results ~/hc_results \
#       --staging-dir output/hc_collect/2026-07-28

set -euo pipefail

SSH_HOST=""
REMOTE_RESULTS=""
STAGING_DIR=""

log_info()  { printf '[%s] [INFO ] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2; }
log_warn()  { printf '[%s] [WARN ] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2; }
log_error() { printf '[%s] [ERROR] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ssh-host)       SSH_HOST="$2"; shift 2 ;;
        --remote-results) REMOTE_RESULTS="$2"; shift 2 ;;
        --staging-dir)    STAGING_DIR="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 --ssh-host user@host --remote-results ~/hc_results --staging-dir output/hc_collect/DATE"
            exit 0
            ;;
        *) log_warn "Unknown argument: $1"; shift ;;
    esac
done

if [[ -z "$SSH_HOST" || -z "$REMOTE_RESULTS" || -z "$STAGING_DIR" ]]; then
    log_error "--ssh-host, --remote-results, and --staging-dir are all required."
    exit 1
fi

TARBALL_REMOTE="${REMOTE_RESULTS}.tar.gz"

log_info "Staging directory: ${STAGING_DIR} (cleared and recreated)"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

if ssh "$SSH_HOST" "[ -f ${TARBALL_REMOTE} ]" 2>/dev/null; then
    log_info "Found remote tarball: ${SSH_HOST}:${TARBALL_REMOTE}"
    LOCAL_TARBALL="$(mktemp -t hc_fetch_XXXX.tar.gz)"
    trap 'rm -f "$LOCAL_TARBALL"' EXIT

    log_info "Downloading tarball → ${LOCAL_TARBALL}"
    rsync -av --info=progress2 "${SSH_HOST}:${TARBALL_REMOTE}" "$LOCAL_TARBALL"

    log_info "Extracting tarball into ${STAGING_DIR}"
    tar -xzf "$LOCAL_TARBALL" -C "$STAGING_DIR" --strip-components=1

    rm -f "$LOCAL_TARBALL"
    trap - EXIT
    log_info "Tarball fetch complete → ${STAGING_DIR}"
else
    log_warn "No tarball found at ${SSH_HOST}:${TARBALL_REMOTE} — falling back to raw directory sync."
    log_info "Syncing ${SSH_HOST}:${REMOTE_RESULTS}/ → ${STAGING_DIR}/"
    rsync -av --delete --info=progress2 "${SSH_HOST}:${REMOTE_RESULTS}/" "${STAGING_DIR}/"
    log_info "Raw sync complete → ${STAGING_DIR}"
fi

if [[ ! -f "${STAGING_DIR}/manifest.json" ]]; then
    log_warn "manifest.json not found in ${STAGING_DIR} — results may be incomplete or in an unexpected layout."
fi

log_info "=== Done ==="
log_info "Results staged at: ${STAGING_DIR}"
