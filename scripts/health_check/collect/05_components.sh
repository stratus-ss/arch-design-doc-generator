#!/usr/bin/env bash
# HC-05: Component Assessment — Chapter 7.3
# Collects: operator health, etcd, registry, monitoring, ingress, storage, network
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="05_components"
hc_init "$CATEGORY"

# Cluster operators and CRDs
hc_capture_json "$CATEGORY" "cluster_operators"           get co
hc_capture_json "$CATEGORY" "machineconfig"               get mc

# Etcd health
hc_capture_json "$CATEGORY" "etcd_pods"                   get pods -n openshift-etcd
hc_capture_text "$CATEGORY" "etcd_status"                 $HC_CLI -n openshift-etcd get pods -o wide

# Image registry
hc_capture_json "$CATEGORY" "imageregistry"               get configs.imageregistry.operator.openshift.io cluster

# Monitoring
hc_capture_json "$CATEGORY" "prometheus"                  get prometheus -n openshift-monitoring
hc_capture_json "$CATEGORY" "prometheusrule"              get prometheusrule -n openshift-monitoring
hc_capture_json "$CATEGORY" "alertmanager"                get alertmanager -n openshift-monitoring

# Ingress
hc_capture_json "$CATEGORY" "ingresscontroller"           get ingresscontroller -n openshift-ingress-operator

# Storage
hc_capture_json "$CATEGORY" "storageclass"                get storageclass
hc_capture_json "$CATEGORY" "pv"                          get pv
hc_capture_json "$CATEGORY" "pvc"                         get pvc -A

# Networking
hc_capture_json "$CATEGORY" "network"                     get network cluster
hc_capture_json "$CATEGORY" "clusternetwork"              get clusternetwork || true
hc_capture_json "$CATEGORY" "network_operator"            get network.operator cluster
hc_capture_json "$CATEGORY" "nncp"                        get nncp || true
hc_capture_json "$CATEGORY" "net_attach_def"              get net-attach-def -A || true

# DNS
hc_capture_json "$CATEGORY" "dns_operator"                get dns.operator cluster
hc_capture_json "$CATEGORY" "dns_config"                  get dns cluster

# CRDs and deprecated APIs
hc_capture_json "$CATEGORY" "crds"                        get crd
hc_capture_json "$CATEGORY" "apirequestcounts"            get apirequestcounts || true

# Webhooks
hc_capture_json "$CATEGORY" "validatingwebhooks"          get validatingwebhookconfigurations || true
hc_capture_json "$CATEGORY" "mutatingwebhooks"            get mutatingwebhookconfigurations || true

# Monitoring config
hc_capture_json "$CATEGORY" "monitoring_config"           get configmap cluster-monitoring-config -n openshift-monitoring || true

hc_summary "$CATEGORY"
