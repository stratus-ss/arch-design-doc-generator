#!/usr/bin/env bash
# HC-10: Metrics Collection — Chapter 7.8
#
# Most metrics collection requires live cluster exec (Prometheus, etcdctl)
# which is not available via omc. This script collects what it can from
# the must-gather static data.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="10_metrics"
hc_init "$CATEGORY"

# Prometheus/Thanos queries and etcdctl exec are not available in omc.
# Collect static pod and config data that may be present in the must-gather.

hc_capture_json "$CATEGORY" "etcd_pods"              get pods -n openshift-etcd
hc_capture_json "$CATEGORY" "monitoring_pods"        get pods -n openshift-monitoring
hc_capture_json "$CATEGORY" "prometheusrule"         get prometheusrule -n openshift-monitoring

hc_info "NOTE: Live Prometheus queries and etcdctl commands are not available via omc."
hc_info "      For full metrics, run the original collect scripts against a live cluster."

hc_summary "$CATEGORY"
