#!/usr/bin/env bash
# HC-09: Security and Compliance Assessment — Chapter 7.7
# Collects: SCC detail, OAuth, compliance scans, cluster role bindings
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="09_security"
hc_init "$CATEGORY"

# SCC modifications and detail
hc_capture_json "$CATEGORY" "scc"                    get scc

# Identity providers / OAuth config
hc_capture_json "$CATEGORY" "oauth"                  get oauth cluster

# Cluster role bindings (access audit)
hc_capture_json "$CATEGORY" "clusterrolebindings"    get clusterrolebinding

# Role bindings across all namespaces
hc_capture_json "$CATEGORY" "rolebindings"           get rolebinding -A

# Compliance operator (if installed)
hc_capture_json "$CATEGORY" "compliance_scans"       get compliancescan -A
hc_capture_json "$CATEGORY" "compliance_suites"      get compliancesuite -A

# Pod security admission / namespace labels
hc_capture_json "$CATEGORY" "namespaces"             get namespaces

# Secrets (count only — not content)
hc_capture_text "$CATEGORY" "secrets_count"          $HC_CLI get secrets -A --no-headers

# Service accounts with cluster-admin bindings
hc_capture_json "$CATEGORY" "clusterrolebindings_admin" get clusterrolebinding

hc_summary "$CATEGORY"
