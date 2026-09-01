#!/usr/bin/env bash
# HC-06: Layered Products Assessment — Chapter 7.4
# Collects: CNV, ACM, ACS, logging, pipelines, OADP
# Gracefully skips products that are not installed (writes _hc_error envelope).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="06_layered"
hc_init "$CATEGORY"

# ---------------------------------------------------------------------------
# Quay application pods: merge labeled + per-registry-namespace Lists
# ---------------------------------------------------------------------------
hc_capture_quay_pods() {
    local category="$1"
    local registry_path="${HC_RESULTS_DIR}/${category}/quay_registry.json"
    local output_path="${HC_RESULTS_DIR}/${category}/quay_pods.json"
    local metadata_path="${HC_RESULTS_DIR}/${category}/quay_pods.meta.json"
    local staging_directory
    local namespaces_file
    local live_registry_path
    local labeled_pods_path
    local namespace
    local member_index=0
    local script_path="${BASH_SOURCE[1]-}"
    if [[ -z "$script_path" ]]; then
        script_path="$0"
    fi

    hc_info "  collect: merged quay_pods List → ${category}/quay_pods.json"
    staging_directory="$(mktemp -d)"
    namespaces_file="${staging_directory}/namespaces.txt"
    live_registry_path="${staging_directory}/live_registry.json"
    labeled_pods_path="${staging_directory}/labeled_pods.json"

    oc get quayregistry -A -o json >"${live_registry_path}" 2>/dev/null || true

    python3 -c "
import json
import sys
from pathlib import Path

def load_payload(path):
    file_path = Path(path)
    if not file_path.is_file() or file_path.stat().st_size == 0:
        return {}
    try:
        return json.loads(file_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}

def add_namespace(name, ordered, seen):
    if not name or name in seen:
        return
    seen.add(name)
    ordered.append(name)

def namespaces_from_registry(payload, ordered, seen):
    items = payload.get('items')
    if not isinstance(items, list):
        items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        metadata = item.get('metadata') or {}
        spec = item.get('spec') or {}
        add_namespace(metadata.get('namespace'), ordered, seen)
        add_namespace(spec.get('targetNamespace'), ordered, seen)

ordered = []
seen = set()
namespaces_from_registry(load_payload(sys.argv[1]), ordered, seen)
namespaces_from_registry(load_payload(sys.argv[2]), ordered, seen)
if not ordered:
    for default_name in ('quay-enterprise', 'quay-registry'):
        add_namespace(default_name, ordered, seen)
Path(sys.argv[3]).write_text('\\n'.join(ordered) + '\\n', encoding='utf-8')
" "$registry_path" "$live_registry_path" "$namespaces_file"

    oc get pods -A -l quay-component -o json >"${labeled_pods_path}" 2>/dev/null || true

    if [[ -f "$namespaces_file" ]]; then
        while IFS= read -r namespace; do
            [[ -z "$namespace" ]] && continue
            oc get pods -n "${namespace}" -o json \
                >"${staging_directory}/namespace_pods_${member_index}.json" 2>/dev/null || true
            member_index=$((member_index + 1))
        done < "$namespaces_file"
    fi

    python3 -c "
import json
import sys
from pathlib import Path

staging_directory = Path(sys.argv[1])
output_path = Path(sys.argv[2])
merged = []
seen_keys = set()

def pod_key(pod):
    metadata = pod.get('metadata') or {}
    uid = metadata.get('uid')
    if uid:
        return ('uid', uid)
    return ('name', metadata.get('namespace', ''), metadata.get('name', ''))

for path in sorted(staging_directory.glob('*.json')):
    if path.name == 'live_registry.json':
        continue
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        continue
    items = payload.get('items')
    if not isinstance(items, list):
        continue
    for pod in items:
        if not isinstance(pod, dict):
            continue
        key = pod_key(pod)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(pod)

output_path.write_text(
    json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': merged}, indent=2)
    + '\\n',
    encoding='utf-8',
)
" "$staging_directory" "$output_path"

    rm -rf "$staging_directory"
    HC_COLLECTED=$((HC_COLLECTED + 1))
    hc_write_capture_metadata "$metadata_path" \
        "oc get pods (quay-component + per QuayRegistry namespace) merged List" \
        "$script_path" "$category" "quay_pods"
}

# CNV / OpenShift Virtualization
hc_capture_json "$CATEGORY" "cnv_hyperconverged"     get hyperconverged -n openshift-cnv
hc_capture_json "$CATEGORY" "cnv_kubevirt"           get kubevirt -n openshift-cnv
hc_capture_json "$CATEGORY" "cnv_pods"               get pods -n openshift-cnv
hc_capture_json "$CATEGORY" "cnv_vm"                 get vm -A
hc_capture_json "$CATEGORY" "cnv_vmi"                get vmi -A
hc_capture_json "$CATEGORY" "cnv_cdi"                get cdi -n openshift-cnv || true
hc_capture_json "$CATEGORY" "cnv_virt_handler_ds"    get ds virt-handler -n openshift-cnv || true

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
hc_capture_quay_pods "$CATEGORY"

# OCP AI / OpenShift AI
hc_capture_json "$CATEGORY" "datasciencecluster"     get datasciencecluster -A || true

# ODF / OpenShift Data Foundation
hc_capture_json "$CATEGORY" "odf_storagecluster"     get storagecluster -A

# RHOSO / Red Hat OpenStack Services on OpenShift
hc_capture_json "$CATEGORY" "rhoso_controlplane"     get openstackcontrolplane -A

# MTV / Migration Toolkit for Virtualization
hc_capture_json "$CATEGORY" "mtv_controller"         get forkliftcontroller -A

# OADP / Velero
hc_capture_json "$CATEGORY" "oadp_dpa"               get dataprotectionapplication -A
hc_capture_json "$CATEGORY" "oadp_csv"               get csv -n openshift-adp
hc_capture_json "$CATEGORY" "backupstoragelocation"  get backupstoragelocation -A

hc_summary "$CATEGORY"
