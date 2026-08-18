#!/usr/bin/env bash
# HC-04: Topology Assessment — Chapter 7.2
# Collects: node roles, machine configs, machine config pools, kubelet configs, etcd
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="04_topology"
hc_init "$CATEGORY"

# Node roles and topology
hc_capture_json "$CATEGORY" "nodes"                  get nodes
hc_capture_text "$CATEGORY" "node_labels"            $HC_CLI get nodes --show-labels

# Machine config
hc_capture_json "$CATEGORY" "machineconfig"          get machineconfig
hc_capture_json "$CATEGORY" "machineconfigpool"      get machineconfigpool
hc_capture_json "$CATEGORY" "kubeletconfig"          get kubeletconfig

# Etcd member count and health (HA check)
hc_capture_json "$CATEGORY" "etcd"                   get etcd cluster
hc_capture_json "$CATEGORY" "etcd_pods"              get pods -n openshift-etcd

hc_summary "$CATEGORY"
