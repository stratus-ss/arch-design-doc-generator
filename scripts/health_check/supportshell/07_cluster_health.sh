#!/usr/bin/env bash
# HC-07: Cluster Health Assessment — Chapter 7.5
# Collects: kubelet versions, firing alerts, pod restarts, master taints
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="07_cluster_health"
hc_init "$CATEGORY"

# Kubelet versions across all nodes
hc_capture_json "$CATEGORY" "nodes"                  get nodes

# Node conditions (NotReady, MemoryPressure, DiskPressure, etc.)
hc_capture_json "$CATEGORY" "node_conditions"        get nodes

# Pod restarts — capture all pods with status
hc_capture_json "$CATEGORY" "pods_all"               get pods -A

# Pod disruption budgets
hc_capture_json "$CATEGORY" "pdb"                    get pdb -A

# Master node taint check (schedulable masters = bad practice)
hc_capture_json "$CATEGORY" "master_nodes"           get nodes -l node-role.kubernetes.io/master

# Cluster version and update history
hc_capture_json "$CATEGORY" "clusterversion"         get clusterversion

# Co degraded check
hc_capture_json "$CATEGORY" "clusteroperators"       get clusteroperator

# Prometheus alerts via API (best-effort; requires monitoring stack; oc live cluster only)
if [[ "$HC_CLI" == oc ]]; then
    hc_capture_text "$CATEGORY" "firing_alerts" \
        oc -n openshift-monitoring exec \
            "$(oc get pods -n openshift-monitoring -l prometheus=k8s -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo '')" \
            -c prometheus -- \
            curl -s http://localhost:9090/api/v1/alerts 2>/dev/null || true
else
    hc_info "Prometheus alerts — not available via omc (requires live cluster exec)"
fi

# Events for pruning signal
hc_capture_json "$CATEGORY" "events"                 get events -A || true

# Jobs for stale job pruning check
hc_capture_json "$CATEGORY" "jobs"                   get jobs -A || true

hc_summary "$CATEGORY"
