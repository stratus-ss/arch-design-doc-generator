#!/usr/bin/env bash
# HC-11: Node Hardware Inventory — Chapter 7.9
#
# Uses oc debug node to collect hardware identity from /sys/class/dmi/id
# and /proc on each node. One JSON file per node.
# All commands are read-only (debug pod is ephemeral, no host state changed).
#
# NOTE: Each oc debug node call takes 5–30 seconds. With many nodes this step
#       will be the slowest in the collection pipeline.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="11_hardware"
hc_init "$CATEGORY"

# ---------------------------------------------------------------------------
# Python helper: parse fixed-order text output into JSON
# Called as: echo "$raw" | python3 "$PARSE_PY" <node> <short_name>
# ---------------------------------------------------------------------------

PARSE_PY="$(mktemp --suffix=.py)"
cat > "$PARSE_PY" << 'PYEOF'
import sys, json

node = sys.argv[1]
short_name = sys.argv[2]
lines = sys.stdin.read().splitlines()

hw = {
    "node":         node,
    "short_name":   short_name,
    "vendor":       lines[0].strip()  if len(lines) > 0 else "",
    "product":      lines[1].strip()  if len(lines) > 1 else "",
    "bios_version": lines[2].strip()  if len(lines) > 2 else "",
    "bios_date":    lines[3].strip()  if len(lines) > 3 else "",
    "cpu_model":    lines[4].strip()  if len(lines) > 4 else "",
}

try:    hw["cpu_cores"]  = int(lines[5]) if len(lines) > 5 else 0
except: hw["cpu_cores"]  = 0
try:    hw["memory_mb"]  = int(lines[6]) if len(lines) > 6 else 0
except: hw["memory_mb"]  = 0

# disk lines: everything between index 7 and the last line (which is hostname)
disks = []
if len(lines) > 8:
    for dl in lines[7:-1]:
        parts = dl.split()
        if len(parts) >= 2:
            disks.append({
                "name": parts[0],
                "size": parts[1],
                "rotational": parts[2] == "1" if len(parts) > 2 else True,
                "type": "HDD" if (parts[2] == "1" if len(parts) > 2 else True) else "SSD/NVMe",
            })
hw["disks"] = disks
hw["dmi_hostname"] = lines[-1].strip() if lines else ""
hw["memory_gb"] = round(hw["memory_mb"] / 1024, 1)

print(json.dumps(hw, indent=2))
PYEOF

# ---------------------------------------------------------------------------
# The script run inside the debug container (fixed-order, one value per line)
# ---------------------------------------------------------------------------

_HW_SCRIPT='cat /sys/class/dmi/id/sys_vendor
cat /sys/class/dmi/id/product_name
cat /sys/class/dmi/id/bios_version
cat /sys/class/dmi/id/bios_date
awk -F: "/model name/{gsub(/ +/,\" \",\$2); print \$2; exit}" /proc/cpuinfo
grep -c "^processor" /proc/cpuinfo
awk "/MemTotal/{print int(\$2/1024)}" /proc/meminfo
lsblk -d -o NAME,SIZE,ROTA -n -e 7,11
hostname'

# ---------------------------------------------------------------------------
# Collect hardware for one node
# ---------------------------------------------------------------------------

hc_collect_node_hw() {
    local node="$1"
    local short_name="${node%%.*}"
    local out="${HC_RESULTS_DIR}/${CATEGORY}/node_hw_${short_name}.json"

    hc_info "  debug node: ${node} → ${CATEGORY}/node_hw_${short_name}.json"

    local tmp_raw
    tmp_raw="$(mktemp)"
    local exit_code=0

    oc debug --quiet node/"${node}" -- chroot /host sh -c "${_HW_SCRIPT}" \
        > "$tmp_raw" 2>/dev/null || exit_code=$?

    if [[ $exit_code -ne 0 || ! -s "$tmp_raw" ]]; then
        printf '{"_hc_error": true, "node": "%s", "note": "oc debug node failed (exit %d)", "timestamp": "%s"}\n' \
            "$node" "$exit_code" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$out"
        hc_warn "  oc debug failed (exit_code=${exit_code}) for ${node}"
        HC_ERRORS=$((HC_ERRORS + 1))
        rm -f "$tmp_raw"
        return
    fi

    local json_out
    json_out="$(python3 "$PARSE_PY" "$node" "$short_name" < "$tmp_raw" 2>/dev/null)"
    rm -f "$tmp_raw"

    if [[ -n "$json_out" ]]; then
        printf '%s\n' "$json_out" > "$out"
        HC_COLLECTED=$((HC_COLLECTED + 1))
        local summary
        summary="$(python3 -c "
import json, sys
d = json.load(sys.stdin)
vendor  = d.get('vendor','?')
product = d.get('product','?')
cpu     = d.get('cpu_model','?').strip()
cores   = d.get('cpu_cores', 0)
mem     = d.get('memory_gb', 0)
disks   = ', '.join(f\"{dk['name']} {dk['size']} ({dk['type']})\" for dk in d.get('disks',[]))
print(f'{vendor} {product} | CPU: {cpu} ({cores} cores) | RAM: {mem}G | Disks: {disks}')
" <<< "$json_out" 2>/dev/null || echo "parsed")"
        hc_info "  ${short_name}: ${summary}"
    else
        printf '{"_hc_error": true, "node": "%s", "note": "JSON parse failed", "timestamp": "%s"}\n' \
            "$node" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$out"
        hc_warn "  JSON parse failed for ${node}"
        HC_ERRORS=$((HC_ERRORS + 1))
    fi
}

# ---------------------------------------------------------------------------
# Iterate over all nodes
# ---------------------------------------------------------------------------

node_list="$(oc get nodes -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)" || {
    hc_error "Failed to list nodes"
    rm -f "$PARSE_PY"
    exit 1
}

node_count=0
for node in $node_list; do
    hc_collect_node_hw "$node"
    node_count=$((node_count + 1))
done

rm -f "$PARSE_PY"
hc_info "Hardware inventory collected for ${node_count} node(s)"
hc_summary "$CATEGORY"
