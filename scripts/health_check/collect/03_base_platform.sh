#!/usr/bin/env bash
# HC-03: Base Platform Assessment — Chapter 7.1
# Collects: cluster version, operators, subscriptions, infrastructure, nodes, SCCs, OAuth
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="03_base_platform"
hc_init "$CATEGORY"

# 7.1.1 — Cluster identification and release
hc_capture_json "$CATEGORY" "clusterversion"         get clusterversion
hc_capture_json "$CATEGORY" "clusteroperators"       get clusteroperator

# 7.1.2 — Subscriptions / installed operators
hc_capture_json "$CATEGORY" "subscriptions"          get subscription -A
hc_capture_json "$CATEGORY" "csv"                    get csv -A

# 7.1.3 — Infrastructure and platform
hc_capture_json "$CATEGORY" "infrastructure"         get infrastructure cluster
hc_capture_json "$CATEGORY" "install_config"         get configmap cluster-config-v1 -n kube-system
hc_capture_json "$CATEGORY" "scheduler"              get scheduler cluster
hc_capture_json "$CATEGORY" "proxy"                  get proxy cluster

# 7.1.4 — Nodes (hardware specs)
hc_capture_json "$CATEGORY" "nodes"                  get nodes
hc_capture_text "$CATEGORY" "nodes_wide"             $HC_CLI get nodes -o wide
hc_capture_json "$CATEGORY" "csr"                    get csr

# 7.1.5 — SCCs and authentication
hc_capture_json "$CATEGORY" "scc"                    get scc
hc_capture_json "$CATEGORY" "oauth"                  get oauth cluster

hc_summary "$CATEGORY"
