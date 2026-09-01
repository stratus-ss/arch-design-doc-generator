#!/usr/bin/env bash
# HC-08: Day-2 Operations Assessment — Chapter 7.6
# Collects: resource quotas, limit ranges, image pruning, upgrade history, resource utilization,
#           live node_image_gc (kubelet HIGH + imageFs used percent; no raw configz/summary dumps),
#           redacted Alertmanager receiver names (no decoded YAML or URLs)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="08_day2"
hc_init "$CATEGORY"

# ---------------------------------------------------------------------------
# Helper: per-node kubelet GC HIGH + imageFs used% (counts/bytes/percent only)
# ---------------------------------------------------------------------------
hc_node_image_gc_stats() {
    local category="$1"
    local check_name="$2"
    local output_path="${HC_RESULTS_DIR}/${category}/${check_name}.json"
    local high_default_percent=85
    local early_warning_percent=50
    local nodes_exit=0
    local node_list=""
    local staging_dir
    local node_name
    local configz_path
    local summary_path
    local member_index=0
    local fetch_rows=""

    hc_info "  node-image-gc: ${check_name} → ${category}/${check_name}.json"

    node_list="$(oc get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null)" || nodes_exit=$?
    if [[ "$nodes_exit" -ne 0 ]] || ! printf '%s' "$node_list" | grep -q '[^[:space:]]'; then
        python3 -c "
import json
import sys
from pathlib import Path
output_path = Path(sys.argv[1])
note = sys.argv[2]
payload = {
    '_hc_error': True,
    'note': note,
    'high_default_percent': int(sys.argv[3]),
    'early_warning_percent': int(sys.argv[4]),
    'members': [],
}
output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
" "$output_path" "oc get nodes failed or returned empty" \
            "$high_default_percent" "$early_warning_percent"
        hc_warn "  node-image-gc: oc get nodes failed or returned empty"
        HC_ERRORS=$((HC_ERRORS + 1))
        HC_COLLECTED=$((HC_COLLECTED + 1))
        return 0
    fi

    staging_dir="$(mktemp -d)"
    while IFS= read -r node_name; do
        [[ -z "$node_name" ]] && continue
        configz_path="${staging_dir}/${member_index}.configz"
        summary_path="${staging_dir}/${member_index}.summary"
        if ! oc get --raw "/api/v1/nodes/${node_name}/proxy/configz" >"$configz_path" 2>/dev/null; then
            rm -f "$configz_path"
            configz_path="-"
        fi
        if ! oc get --raw "/api/v1/nodes/${node_name}/proxy/stats/summary" >"$summary_path" 2>/dev/null; then
            rm -f "$summary_path"
            summary_path="-"
        fi
        fetch_rows+="${node_name}"$'\t'"${configz_path}"$'\t'"${summary_path}"$'\n'
        member_index=$((member_index + 1))
    done <<< "$node_list"

    python3 -c "
import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
high_default_percent = int(sys.argv[2])
early_warning_percent = int(sys.argv[3])


def load_json(file_path):
    if file_path in ('', '-'):
        return None
    path = Path(file_path)
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def high_percent_from_configz(configz_payload):
    if not isinstance(configz_payload, dict):
        return high_default_percent
    kubelet_config = configz_payload.get('kubeletconfig') or {}
    if not isinstance(kubelet_config, dict):
        return high_default_percent
    high_value = kubelet_config.get('imageGCHighThresholdPercent')
    if isinstance(high_value, bool) or not isinstance(high_value, (int, float)):
        return high_default_percent
    return int(high_value)


def image_filesystem(summary_payload):
    if not isinstance(summary_payload, dict):
        return None
    node_stats = summary_payload.get('node') or {}
    if not isinstance(node_stats, dict):
        return None
    runtime_stats = node_stats.get('runtime') or {}
    image_fs = None
    if isinstance(runtime_stats, dict):
        image_fs = runtime_stats.get('imageFs')
    if not isinstance(image_fs, dict):
        image_fs = node_stats.get('fs')
    if not isinstance(image_fs, dict):
        return None
    return image_fs


def kubelet_reserved_excerpt(configz_payload):
    memory_value = ''
    auto_sizing_reserved = None
    if not isinstance(configz_payload, dict):
        return memory_value, auto_sizing_reserved
    kubelet_config = configz_payload.get('kubeletconfig') or {}
    if not isinstance(kubelet_config, dict):
        return memory_value, auto_sizing_reserved
    system_reserved = kubelet_config.get('systemReserved')
    if isinstance(system_reserved, dict):
        memory = system_reserved.get('memory')
        if isinstance(memory, str):
            memory_value = memory
    auto_value = kubelet_config.get('autoSizingReserved')
    if isinstance(auto_value, bool):
        auto_sizing_reserved = auto_value
    return memory_value, auto_sizing_reserved


def apply_reserved_excerpt(member, configz_payload):
    memory_value, auto_sizing_reserved = kubelet_reserved_excerpt(configz_payload)
    member['system_reserved_memory'] = memory_value
    if auto_sizing_reserved is not None:
        member['auto_sizing_reserved'] = auto_sizing_reserved


members = []
for line in sys.stdin.read().splitlines():
    if not line.strip():
        continue
    node_name, configz_file, summary_file = line.split('\t')
    configz_payload = load_json(configz_file)
    summary_payload = load_json(summary_file)
    member = {
        'node': node_name,
        'high_percent': high_percent_from_configz(configz_payload),
    }
    apply_reserved_excerpt(member, configz_payload)
    image_fs = image_filesystem(summary_payload)
    if image_fs is None:
        member['_hc_error'] = True
        members.append(member)
        continue
    capacity_bytes = image_fs.get('capacityBytes')
    available_bytes = image_fs.get('availableBytes')
    if not isinstance(capacity_bytes, (int, float)) or not isinstance(available_bytes, (int, float)):
        member['_hc_error'] = True
        members.append(member)
        continue
    capacity_bytes = int(capacity_bytes)
    available_bytes = int(available_bytes)
    member['capacity_bytes'] = capacity_bytes
    member['available_bytes'] = available_bytes
    if capacity_bytes > 0:
        member['used_percent'] = max(0, int((capacity_bytes - available_bytes) * 100 / capacity_bytes))
    members.append(member)

payload = {
    'high_default_percent': high_default_percent,
    'early_warning_percent': early_warning_percent,
    'members': members,
}
output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
" "$output_path" "$high_default_percent" "$early_warning_percent" <<< "$fetch_rows"

    rm -rf "$staging_dir"
    HC_COLLECTED=$((HC_COLLECTED + 1))
}

# ---------------------------------------------------------------------------
# Helper: Alertmanager receiver names only (never persist YAML or URLs)
# ---------------------------------------------------------------------------
hc_alertmanager_receiver_names() {
    local category="$1"
    local check_name="$2"
    local output_path="${HC_RESULTS_DIR}/${category}/${check_name}.json"
    local secret_exit=0
    local secret_json=""

    hc_info "  alertmanager-receivers: ${check_name} → ${category}/${check_name}.json"

    secret_json="$(oc -n openshift-monitoring get secret alertmanager-main -o json 2>/dev/null)" || secret_exit=$?
    if [[ "$secret_exit" -ne 0 ]]; then
        python3 -c "$(cat <<'PY'
import json
import sys
from pathlib import Path
output_path = Path(sys.argv[1])
note = sys.argv[2]
payload = {
    "_hc_error": True,
    "receiver_names": [],
    "note": note,
}
output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
)" "$output_path" "oc get secret alertmanager-main failed"
        hc_warn "  alertmanager-receivers: oc get secret alertmanager-main failed"
        HC_ERRORS=$((HC_ERRORS + 1))
        HC_COLLECTED=$((HC_COLLECTED + 1))
        return 0
    fi

    printf '%s' "$secret_json" | python3 -c "$(cat <<'PY'
import base64
import json
import re
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
receiver_name_pattern = re.compile(r'^\s*-\s*"?name"?\s*:\s*(\S+)')
top_level_key_pattern = re.compile(r'^"?([A-Za-z_][\w-]*)"?\s*:')


def write_payload(payload):
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_error(note):
    write_payload({"_hc_error": True, "receiver_names": [], "note": note})


try:
    secret_payload = json.loads(sys.stdin.read())
except (json.JSONDecodeError, TypeError, ValueError):
    write_error("alertmanager secret JSON parse failed")
    raise SystemExit(0)

if not isinstance(secret_payload, dict):
    write_error("alertmanager secret JSON is not an object")
    raise SystemExit(0)

secret_data = secret_payload.get("data")
if not isinstance(secret_data, dict):
    write_error("alertmanager secret data missing")
    raise SystemExit(0)

encoded_yaml = secret_data.get("alertmanager.yaml")
if not isinstance(encoded_yaml, str) or not encoded_yaml:
    write_error("alertmanager.yaml key missing from secret data")
    raise SystemExit(0)

try:
    padding = "=" * ((4 - len(encoded_yaml) % 4) % 4)
    decoded_bytes = base64.b64decode(encoded_yaml + padding)
    yaml_text = decoded_bytes.decode("utf-8")
except (ValueError, UnicodeDecodeError, TypeError):
    write_error("alertmanager.yaml base64 decode failed")
    raise SystemExit(0)

receiver_names = []
in_receivers_block = False
for line in yaml_text.splitlines():
    top_level_match = top_level_key_pattern.match(line)
    if top_level_match:
        key_name = top_level_match.group(1)
        in_receivers_block = key_name == "receivers"
        continue
    if not in_receivers_block:
        continue
    name_match = receiver_name_pattern.match(line)
    if not name_match:
        continue
    token = name_match.group(1).strip().strip('"').strip("'")
    if not token:
        continue
    lowered = token.lower()
    if "http://" in lowered or "https://" in lowered:
        continue
    receiver_names.append(token)

write_payload({"receiver_names": receiver_names})
PY
)" "$output_path"
    unset secret_json
    HC_COLLECTED=$((HC_COLLECTED + 1))
}

# Resource quotas and limit ranges
hc_capture_json "$CATEGORY" "resourcequota"          get resourcequota -A
hc_capture_json "$CATEGORY" "limitrange"             get limitrange -A
hc_capture_json "$CATEGORY" "networkpolicy"          get networkpolicy -A

# Cluster pruning / image config
hc_capture_json "$CATEGORY" "image_config"           get image.config.openshift.io cluster
hc_alertmanager_receiver_names "$CATEGORY" "alertmanager_receivers"

# Upgrade history (via clusterversion)
hc_capture_json "$CATEGORY" "clusterversion"         get clusterversion

# Cluster-level resource usage (best-effort; requires metrics-server; oc live cluster only)
if [[ "$HC_CLI" == oc ]]; then
    hc_capture_text "$CATEGORY" "top_nodes"              oc adm top nodes
    hc_capture_text "$CATEGORY" "top_pods"               oc adm top pods -A --sort-by=memory
    hc_node_image_gc_stats "$CATEGORY" "node_image_gc"
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
