#!/usr/bin/env bash
# HC-10: Metrics Collection — Chapter 7.8
#
# Collects real-time metrics via oc exec into Prometheus/Thanos and etcd pods.
# All commands are read-only. No cluster state is modified.
#
# Data collected:
#   - Node CPU and memory requests (% of allocatable) from Prometheus
#   - etcd disk WAL fsync P99 latency per pod
#   - etcd compaction p95 (PromQL)
#   - etcd log phrase counts (6h, counts only; no log body)
#   - etcd DB size and leader changes
#   - API server request P99 latency
#   - Certificate expiry (days to expiry)
#   - etcd endpoint health and status via etcdctl
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="10_metrics"
hc_init "$CATEGORY"

# ---------------------------------------------------------------------------
# Helper: run a PromQL instant query via Thanos querier exec
# Returns JSON from the Prometheus HTTP API.
# ---------------------------------------------------------------------------
_find_thanos_pod() {
    # Try multiple label selectors across OCP versions
    local pod
    for selector in \
        "app.kubernetes.io/name=thanos-query" \
        "app.kubernetes.io/name=thanos-querier" \
        "app=thanos-querier" \
        "app.kubernetes.io/component=query-layer"
    do
        pod="$(oc get pod -n openshift-monitoring \
            -l "$selector" \
            -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
        if [[ -n "$pod" ]]; then
            echo "$pod"
            return 0
        fi
    done
}

hc_prometheus_query() {
    local category="$1"
    local check_name="$2"
    local query="$3"
    local output_path="${HC_RESULTS_DIR}/${category}/${check_name}.json"

    hc_info "  prom-query: ${check_name} → ${category}/${check_name}.json"

    local thanos_pod
    thanos_pod="$(_find_thanos_pod)"
    if [[ -z "$thanos_pod" ]]; then
        printf '{"_hc_error": true, "note": "Thanos querier pod not found", "timestamp": "%s"}\n' \
            "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$output_path"
        hc_warn "  Thanos querier not found — skipping ${check_name}"
        return
    fi

    local encoded_query
    # URL-encode the query using python3
    encoded_query="$(python3 -c "
import sys, urllib.parse
print(urllib.parse.quote(sys.stdin.read(), safe=''))
" <<< "$query" 2>/dev/null || printf '%s' "$query" | sed 's/ /%20/g; s/{/%7B/g; s/}/%7D/g; s/"/%22/g; s/=/%3D/g; s/\[/%5B/g; s/\]/%5D/g; s|/|%2F|g; s/,/%2C/g; s/|/%7C/g')"

    # Determine the correct container name (thanos-query or thanos-querier)
    local container_name="thanos-query"
    if ! oc exec -n openshift-monitoring "$thanos_pod" -c thanos-query -- true &>/dev/null; then
        container_name="thanos-querier"
    fi

    local exit_code=0
    local result
    result="$(oc exec -n openshift-monitoring "$thanos_pod" -c "$container_name" -- \
        curl -s "http://localhost:9090/api/v1/query?query=${encoded_query}" 2>/dev/null)" || exit_code=$?

    if [[ $exit_code -eq 0 && -n "$result" ]]; then
        printf '%s\n' "$result" > "$output_path"
        HC_COLLECTED=$((HC_COLLECTED + 1))
    else
        printf '{"_hc_error": true, "note": "prometheus query failed (exit %d)", "timestamp": "%s"}\n' \
            "$exit_code" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$output_path"
        hc_warn "  prometheus query failed (exit_code=${exit_code}): ${check_name}"
        HC_ERRORS=$((HC_ERRORS + 1))
    fi
}

# ---------------------------------------------------------------------------
# Helper: run etcdctl inside an etcd pod
# ---------------------------------------------------------------------------
_find_etcd_pod() {
    oc get pod -n openshift-etcd \
        -l app=etcd \
        --field-selector=status.phase=Running \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}

hc_etcdctl() {
    local category="$1"
    local check_name="$2"
    shift 2
    local output_path="${HC_RESULTS_DIR}/${category}/${check_name}.json"

    hc_info "  etcdctl: $* → ${category}/${check_name}.json"

    local etcd_pod
    etcd_pod="$(_find_etcd_pod)"
    if [[ -z "$etcd_pod" ]]; then
        printf '{"_hc_error": true, "note": "No running etcd pod found", "timestamp": "%s"}\n' \
            "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$output_path"
        hc_warn "  No running etcd pod found — skipping ${check_name}"
        return
    fi

    local hostname
    hostname="${etcd_pod#etcd-}"  # strip the etcd- prefix to get the node hostname

    # Find the CA bundle — path varies by OCP version
    local ca_cert=""
    for ca_path in \
        "/etc/kubernetes/static-pod-certs/configmaps/etcd-all-bundles/server-ca-bundle.crt" \
        "/etc/kubernetes/static-pod-certs/configmaps/etcd-serving-ca/ca-bundle.crt" \
        "/etc/etcd/ca.crt"
    do
        if oc exec -n openshift-etcd "$etcd_pod" -- test -f "$ca_path" &>/dev/null; then
            ca_cert="$ca_path"
            break
        fi
    done

    if [[ -z "$ca_cert" ]]; then
        printf '{"_hc_error": true, "note": "CA cert not found in etcd pod", "timestamp": "%s"}\n' \
            "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$output_path"
        hc_warn "  etcd CA cert not found in pod — skipping ${check_name}"
        return
    fi

    local exit_code=0
    local result
    result="$(oc exec -n openshift-etcd "$etcd_pod" -- /bin/sh -c "
        ETCDCTL_ENDPOINTS=https://localhost:2379 \
        ETCDCTL_CACERT=${ca_cert} \
        ETCDCTL_CERT=/etc/kubernetes/static-pod-certs/secrets/etcd-all-certs/etcd-peer-${hostname}.crt \
        ETCDCTL_KEY=/etc/kubernetes/static-pod-certs/secrets/etcd-all-certs/etcd-peer-${hostname}.key \
        etcdctl $* 2>/dev/null
    " 2>/dev/null)" || exit_code=$?

    if [[ $exit_code -eq 0 && -n "$result" ]]; then
        # Wrap text output in JSON envelope
        local escaped_output
        escaped_output="$(printf '%s' "$result" | \
            sed 's/\\/\\\\/g; s/"/\\"/g' | \
            awk '{printf "%s\\n", $0}' | \
            sed 's/\\n$//')"
        printf '{"_hc_text": true, "command": "etcdctl %s", "output": "%s", "exit_code": 0, "timestamp": "%s"}\n' \
            "$*" "$escaped_output" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$output_path"
        HC_COLLECTED=$((HC_COLLECTED + 1))
    else
        printf '{"_hc_error": true, "command": "etcdctl %s", "exit_code": %d, "timestamp": "%s"}\n' \
            "$*" "$exit_code" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$output_path"
        hc_warn "  etcdctl failed (exit_code=${exit_code}): $*"
        HC_ERRORS=$((HC_ERRORS + 1))
    fi
}

# ---------------------------------------------------------------------------
# Helper: count three TSR etcd log phrases over 6h (counts only)
# ---------------------------------------------------------------------------
hc_etcd_log_phrase_counts() {
    local category="$1"
    local check_name="$2"
    local output_path="${HC_RESULTS_DIR}/${category}/${check_name}.json"
    local member_records=""
    local pod_name
    local log_text
    local heartbeat_count
    local timed_out_count
    local rafthttp_count
    local log_failed
    local pod_list

    hc_info "  etcd-log-phrases: ${check_name} → ${category}/${check_name}.json"

    pod_list="$(oc get pod -n openshift-etcd -l app=etcd \
        -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)"

    while IFS= read -r pod_name; do
        [[ -z "$pod_name" ]] && continue
        log_failed=0
        log_text=""
        if ! log_text="$(oc logs -n openshift-etcd "$pod_name" -c etcd --since=6h 2>/dev/null)"; then
            log_failed=1
            log_text=""
        fi
        heartbeat_count="$(printf '%s' "$log_text" | grep -cF 'failed to send out heartbeat on time' || true)"
        timed_out_count="$(printf '%s' "$log_text" | grep -cF 'request timed out' || true)"
        rafthttp_count="$(printf '%s' "$log_text" | grep -cF 'rafthttp: failed to read' || true)"
        member_records+="${pod_name}"$'\t'"${heartbeat_count}"$'\t'"${timed_out_count}"$'\t'"${rafthttp_count}"$'\t'"${log_failed}"$'\n'
    done <<< "$pod_list"

    python3 -c "
import json
import sys
from pathlib import Path
output_path = Path(sys.argv[1])
members = []
for line in sys.stdin.read().splitlines():
    if not line.strip():
        continue
    pod_name, heartbeat, timed_out, rafthttp, log_failed = line.split('\t')
    member = {
        'pod': pod_name,
        'heartbeat': int(heartbeat),
        'timed_out': int(timed_out),
        'rafthttp': int(rafthttp),
    }
    if log_failed == '1':
        member['_hc_error'] = True
    members.append(member)
payload = json.dumps({'since': '6h', 'members': members}, indent=2, ensure_ascii=False)
output_path.write_text(payload + '\n', encoding='utf-8')
" "$output_path" <<< "$member_records"

    HC_COLLECTED=$((HC_COLLECTED + 1))
}

# ---------------------------------------------------------------------------
# 10.1 — Node resource allocation (requests as % of allocatable)
# ---------------------------------------------------------------------------

hc_prometheus_query "$CATEGORY" "node_cpu_requests_pct" \
    'round(sum(kube_pod_container_resource_requests{resource="cpu"}) by (node) / kube_node_status_allocatable{resource="cpu"} * 100, 1)'

hc_prometheus_query "$CATEGORY" "node_memory_requests_pct" \
    'round(sum(kube_pod_container_resource_requests{resource="memory"}) by (node) / kube_node_status_allocatable{resource="memory"} * 100, 1)'

hc_prometheus_query "$CATEGORY" "node_cpu_limits_pct" \
    'round(sum(kube_pod_container_resource_limits{resource="cpu"}) by (node) / kube_node_status_allocatable{resource="cpu"} * 100, 1)'

hc_prometheus_query "$CATEGORY" "node_memory_limits_pct" \
    'round(sum(kube_pod_container_resource_limits{resource="memory"}) by (node) / kube_node_status_allocatable{resource="memory"} * 100, 1)'

# ---------------------------------------------------------------------------
# 10.2 — etcd performance metrics
# ---------------------------------------------------------------------------

hc_prometheus_query "$CATEGORY" "etcd_disk_wal_fsync_p99" \
    'histogram_quantile(0.99, sum(rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m])) by (le, pod))'

hc_prometheus_query "$CATEGORY" "etcd_disk_backend_p99" \
    'histogram_quantile(0.99, sum(rate(etcd_disk_backend_commit_duration_seconds_bucket[5m])) by (le, pod))'

hc_prometheus_query "$CATEGORY" "etcd_leader_changes_1h" \
    'increase(etcd_server_leader_changes_seen_total[1h])'

hc_prometheus_query "$CATEGORY" "etcd_db_size_bytes" \
    'etcd_mvcc_db_total_size_in_bytes'

hc_prometheus_query "$CATEGORY" "etcd_db_size_in_use" \
    'etcd_mvcc_db_total_size_in_use_in_bytes'

hc_prometheus_query "$CATEGORY" "etcd_proposals_failed" \
    'increase(etcd_server_proposals_failed_total[1h])'

hc_prometheus_query "$CATEGORY" "etcd_heartbeat_failures" \
    'increase(etcd_server_heartbeat_send_failures_total[1h])'

hc_prometheus_query "$CATEGORY" "etcd_compaction_p95" \
    'histogram_quantile(0.95, sum(rate(etcd_debugging_mvcc_db_compaction_total_duration_milliseconds_bucket[1h])) by (le, pod)) / 1000'

hc_etcd_log_phrase_counts "$CATEGORY" "etcd_log_phrase_counts"

# ---------------------------------------------------------------------------
# 10.3 — API server performance
# ---------------------------------------------------------------------------

hc_prometheus_query "$CATEGORY" "apiserver_request_latency_p99" \
    'histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket{scope="resource",verb!~"WATCH|CONNECT"}[5m])) by (le, resource, verb))'

hc_prometheus_query "$CATEGORY" "apiserver_error_rate" \
    'sum(rate(apiserver_request_total{code=~"5.."}[5m])) by (resource, verb)'

# ---------------------------------------------------------------------------
# 10.4 — Certificate expiry
# ---------------------------------------------------------------------------

hc_prometheus_query "$CATEGORY" "cert_expiry_days" \
    'sort_desc((apiserver_client_certificate_expiration_seconds_sum / apiserver_client_certificate_expiration_seconds_count - time()) / 86400)'

# ---------------------------------------------------------------------------
# 10.5 — etcd endpoint health and status via etcdctl
# ---------------------------------------------------------------------------

hc_etcdctl "$CATEGORY" "etcd_endpoint_health" \
    "endpoint health --cluster -w json"

hc_etcdctl "$CATEGORY" "etcd_endpoint_status" \
    "endpoint status --cluster -w json"

# ---------------------------------------------------------------------------
# 10.6 — Cluster resource pressure
# ---------------------------------------------------------------------------

hc_prometheus_query "$CATEGORY" "node_memory_working_set_pct" \
    'round(sum(container_memory_working_set_bytes{container=""}) by (node) / kube_node_status_allocatable{resource="memory"} * 100, 1)'

hc_prometheus_query "$CATEGORY" "pvc_utilization_pct" \
    'round(kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes * 100, 1)'

hc_prometheus_query "$CATEGORY" "volume_mount_p99" \
    'histogram_quantile(0.99, sum(rate(storage_operation_duration_seconds_bucket{operation=~"volume_mount|mount"}[15m])) by (le))'

hc_summary "$CATEGORY"
