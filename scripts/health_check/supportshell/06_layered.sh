#!/usr/bin/env bash
# HC-06: Layered Products Assessment — Chapter 7.4
# Collects: CNV, ACM, ACS, logging, pipelines
# Gracefully skips products that are not installed (writes _hc_error envelope).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="06_layered"
hc_init "$CATEGORY"

# CNV / OpenShift Virtualization
hc_capture_json "$CATEGORY" "cnv_hyperconverged"     get hyperconverged -n openshift-cnv
hc_capture_json "$CATEGORY" "cnv_kubevirt"           get kubevirt -n openshift-cnv
hc_capture_json "$CATEGORY" "cnv_pods"               get pods -n openshift-cnv
hc_capture_json "$CATEGORY" "cnv_vm"                 get vm -A
hc_capture_json "$CATEGORY" "cnv_vmi"                get vmi -A

# ACM / Advanced Cluster Management
hc_capture_json "$CATEGORY" "acm_multiclusterhub"    get multiclusterhub -n open-cluster-management
hc_capture_json "$CATEGORY" "acm_pods"               get pods -n open-cluster-management

# ACS / StackRox
hc_capture_json "$CATEGORY" "acs_central"            get central -n stackrox
hc_capture_json "$CATEGORY" "acs_pods"               get pods -n stackrox

# Logging / Loki / Elasticsearch
hc_capture_json "$CATEGORY" "logging_clusterlogging" get clusterlogging instance -n openshift-logging
hc_capture_json "$CATEGORY" "logging_loki"           get lokistack -n openshift-logging
hc_capture_json "$CATEGORY" "logging_pods"           get pods -n openshift-logging

# Pipelines / Tekton
hc_capture_json "$CATEGORY" "pipelines_tektonconfig" get tektonconfig cluster
hc_capture_json "$CATEGORY" "pipelines_pods"         get pods -n openshift-pipelines

# Service Mesh / Istio
hc_capture_json "$CATEGORY" "servicemesh_smcp"       get servicemeshcontrolplane -A
hc_capture_json "$CATEGORY" "servicemesh_pods"       get pods -n istio-system

# Serverless / Knative
hc_capture_json "$CATEGORY" "serverless_knserving"   get knativeserving -A || true
hc_capture_json "$CATEGORY" "serverless_kneventing"  get knativeeventing -A || true

# Quay
hc_capture_json "$CATEGORY" "quay_registry"          get quayregistry -A || true

# OCP AI / OpenShift AI
hc_capture_json "$CATEGORY" "datasciencecluster"     get datasciencecluster -A || true

# ODF / OpenShift Data Foundation
hc_capture_json "$CATEGORY" "odf_storagecluster"     get storagecluster -A

# RHOSO / Red Hat OpenStack Services on OpenShift
hc_capture_json "$CATEGORY" "rhoso_controlplane"     get openstackcontrolplane -A

# MTV / Migration Toolkit for Virtualization
hc_capture_json "$CATEGORY" "mtv_controller"         get forkliftcontroller -A

hc_summary "$CATEGORY"
