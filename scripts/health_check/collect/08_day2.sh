#!/usr/bin/env bash
# HC-08: Day-2 Operations Assessment — Chapter 7.6
# Collects: resource quotas, limit ranges, image pruning, upgrade history, resource utilization
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="08_day2"
hc_init "$CATEGORY"

# Resource quotas and limit ranges
hc_capture_json "$CATEGORY" "resourcequota"          get resourcequota -A
hc_capture_json "$CATEGORY" "limitrange"             get limitrange -A

# Cluster pruning / image config
hc_capture_json "$CATEGORY" "image_config"           get image.config.openshift.io cluster

# Upgrade history (via clusterversion)
hc_capture_json "$CATEGORY" "clusterversion"         get clusterversion

# Cluster-level resource usage (best-effort; requires metrics-server; oc live cluster only)
if [[ "$HC_CLI" == oc ]]; then
    hc_capture_text "$CATEGORY" "top_nodes"              oc adm top nodes
    hc_capture_text "$CATEGORY" "top_pods"               oc adm top pods -A --sort-by=memory
else
    hc_info "Cluster-level resource usage — not available via omc (requires live metrics-server)"
fi

# Certificate expiry check
hc_capture_json "$CATEGORY" "apiserver"              get apiserver cluster
hc_capture_json "$CATEGORY" "proxy"                  get proxy cluster

# Namespace count (sprawl check)
hc_capture_json "$CATEGORY" "namespaces"             get namespaces

# Operator subscriptions (for approval strategy check)
hc_capture_json "$CATEGORY" "subscriptions"          get subscriptions -A

# DeploymentConfigs (deprecated since OCP 4.14)
hc_capture_json "$CATEGORY" "deploymentconfig"       get dc -A || true

# Cert-manager certificates
hc_capture_json "$CATEGORY" "certificates"           get certificates -A || true

hc_summary "$CATEGORY"
