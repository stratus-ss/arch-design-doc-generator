#!/usr/bin/env bash
# HC-12: Optional CCX advisory payload ingestion
# Collects: precomputed CCX rules payload from a local JSON file if provided.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="12_ccx"
hc_init "$CATEGORY"

OUTPUT_PATH="${HC_RESULTS_DIR}/${CATEGORY}/ccx_rules.json"
METADATA_PATH="${HC_RESULTS_DIR}/${CATEGORY}/ccx_rules.meta.json"
SCRIPT_PATH="$0"
COMMAND_STR="ingest ccx rules payload"

if [[ -n "${HC_CCX_RULES_FILE:-}" && -f "${HC_CCX_RULES_FILE}" ]]; then
    cp "${HC_CCX_RULES_FILE}" "$OUTPUT_PATH"
    HC_COLLECTED=$((HC_COLLECTED + 1))
    hc_info "  ingested: ${HC_CCX_RULES_FILE} → ${CATEGORY}/ccx_rules.json"
else
    printf '{"_hc_not_found": true, "note": "HC_CCX_RULES_FILE not provided", "timestamp": "%s"}\n' \
        "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$OUTPUT_PATH"
    hc_info "  optional payload not provided: set HC_CCX_RULES_FILE to ingest CCX rules"
fi

hc_write_capture_metadata "$METADATA_PATH" "$COMMAND_STR" "$SCRIPT_PATH" "$CATEGORY" "ccx_rules"
hc_summary "$CATEGORY"
