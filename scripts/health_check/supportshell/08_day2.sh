#!/usr/bin/env bash
# HC-08: Day-2 Operations Assessment — Chapter 7.6
# Collects: resource quotas, limit ranges, image pruning, upgrade history, resource utilization,
#           redacted Alertmanager receiver names (no decoded YAML or URLs)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="08_day2"
hc_init "$CATEGORY"

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
else
    hc_info "Cluster-level resource usage — not available via omc (requires live metrics-server)"
    hc_info "node_image_gc — live-only (omc cannot query kubelet node proxy)"
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
