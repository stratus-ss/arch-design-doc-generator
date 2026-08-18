#!/usr/bin/env bash
# HC-11: Node Hardware Inventory — Chapter 7.9
#
# Extracts hardware identity from per-node sysinfo.tgz archives in the current
# must-gather selected in omc. Produces one node_hw_<short>.json per node using
# the same downstream shape as the live-cluster collector, minus disks[].
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
CATEGORY="11_hardware"
hc_init "$CATEGORY"

hc_capture_json "$CATEGORY" "nodes"                  get nodes
hc_capture_text "$CATEGORY" "nodes_wide"             $HC_CLI get nodes -o wide

hc_current_mg_path() {
    "$HC_CLI" mg get 2>/dev/null | awk '$1 == "*" {print $3}'
}

PARSE_SCRIPT="$(mktemp --suffix=.py)"
trap 'rm -f "$PARSE_SCRIPT"' EXIT
cat > "$PARSE_SCRIPT" << 'PYEOF'
import json
import sys
import tarfile

tgz_path, node, short_name = sys.argv[1:4]


def _safe_int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _read_suffix(file_members, tarball, *suffixes: str) -> str:
    for member in file_members:
        for suffix in suffixes:
            if member.name.endswith(suffix):
                handle = tarball.extractfile(member)
                if handle is None:
                    continue
                return handle.read().decode("utf-8", "ignore").strip()
    return ""


with tarfile.open(tgz_path, "r:gz") as tarball:
    file_members = [member for member in tarball.getmembers() if member.isfile()]

    vendor = _read_suffix(
        file_members, tarball,
        "sys/class/dmi/id/sys_vendor",
        "sys/class/dmi/id/bios_vendor",
    )
    product = _read_suffix(file_members, tarball, "sys/class/dmi/id/product_name")
    bios_version = _read_suffix(file_members, tarball, "sys/class/dmi/id/bios_version")
    bios_date = _read_suffix(file_members, tarball, "sys/class/dmi/id/bios_date")
    dmi_hostname = _read_suffix(file_members, tarball, "etc/hostname")
    cpuinfo = _read_suffix(file_members, tarball, "proc/cpuinfo")
    machineinfo_raw = _read_suffix(file_members, tarball, "machineinfo.json")

machineinfo = {}
if machineinfo_raw:
    try:
        machineinfo = json.loads(machineinfo_raw)
    except json.JSONDecodeError:
        machineinfo = {}

cpu_model = ""
cpu_cores = 0
for line in cpuinfo.splitlines():
    stripped = line.strip()
    if not cpu_model and stripped.lower().startswith("model name") and ":" in stripped:
        cpu_model = stripped.split(":", 1)[1].strip()
    if stripped.startswith("processor"):
        cpu_cores += 1
if not cpu_cores:
    cpu_cores = _safe_int(machineinfo.get("num_cores") or machineinfo.get("num_threads"))

memory_bytes = _safe_int(machineinfo.get("memory_capacity"))
memory_mb = int(memory_bytes / 1024 / 1024) if memory_bytes else 0

hardware = {
    "node": node,
    "short_name": short_name,
    "vendor": vendor,
    "product": product,
    "bios_version": bios_version,
    "bios_date": bios_date,
    "cpu_model": cpu_model,
    "cpu_cores": cpu_cores,
    "memory_mb": memory_mb,
    "memory_gb": round(memory_mb / 1024, 1),
}
if dmi_hostname:
    hardware["dmi_hostname"] = dmi_hostname

print(json.dumps(hardware, indent=2))
PYEOF

MG_PATH="$(hc_current_mg_path)"
MG_NODES_DIR="${MG_PATH}/nodes"

hc_collect_node_hw() {
    local node="$1"
    local short_name="${node%%.*}"
    local output_path="${HC_RESULTS_DIR}/${CATEGORY}/node_hw_${short_name}.json"
    local sysinfo_tgz="${MG_NODES_DIR}/${node}/sysinfo.tgz"

    if [[ ! -f "$sysinfo_tgz" ]]; then
        printf '{"_hc_not_found": true, "node": "%s", "note": "sysinfo.tgz not present in must-gather", "timestamp": "%s"}\n' \
            "$node" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$output_path"
        hc_info "  ${node}: sysinfo.tgz not present"
        return
    fi

    if python3 "$PARSE_SCRIPT" "$sysinfo_tgz" "$node" "$short_name" > "$output_path" 2>/dev/null; then
        HC_COLLECTED=$((HC_COLLECTED + 1))
        hc_info "  ${node}: wrote ${CATEGORY}/node_hw_${short_name}.json"
    else
        printf '{"_hc_error": true, "node": "%s", "note": "sysinfo.tgz parse failed", "timestamp": "%s"}\n' \
            "$node" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$output_path"
        hc_warn "  ${node}: sysinfo.tgz parse failed"
        HC_ERRORS=$((HC_ERRORS + 1))
    fi
}

if [[ -z "$MG_PATH" || ! -d "$MG_NODES_DIR" ]]; then
    hc_info "NOTE: Active omc must-gather path could not be resolved to a nodes/ directory."
    hc_info "      Detailed hardware extraction requires the OCP must-gather selected in omc."
    hc_summary "$CATEGORY"
    exit 0
fi

node_count=0
for node_dir in "${MG_NODES_DIR}"/*; do
    [[ -d "$node_dir" ]] || continue
    hc_collect_node_hw "$(basename "$node_dir")"
    node_count=$((node_count + 1))
done

hc_info "Hardware inventory collected for ${node_count} node(s) from sysinfo.tgz archives"
hc_summary "$CATEGORY"
