"""Evaluators for 7.9 Hardware Inventory."""
from __future__ import annotations

from hc_report.evaluators._common import _not_applicable
from hc_report.models import CheckResult


def _evaluate_node_hardware_inventory(category_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Hardware inventory from oc debug node: vendor, CPU, memory, disk type."""
    hardware_files = {key: value for key, value in category_data.items() if key.startswith("node_hw_")}
    if not hardware_files:
        return [_not_applicable(f"{category_id}.hw", "Node Hardware Inventory", category_id, category_name,
                    "Hardware inventory not collected — run make hc-collect")]

    checks: list[CheckResult] = []
    for key, hardware in sorted(hardware_files.items()):
        if hardware.get("_hc_error") or hardware.get("_hc_not_found"):
            checks.append(CheckResult(category_id, category_name, f"{category_id}.{key}",
                                      f"Hardware: {key.replace('node_hw_', '')}",
                                      "SKIPPED", "oc debug node failed — manual check required", key))
            continue
        checks += _build_hw_checks(key, hardware, category_id, category_name)
    return checks


def _build_hw_checks(key: str, hardware: dict, category_id: str, category_name: str) -> list[CheckResult]:
    short = hardware.get("short_name", key.replace("node_hw_", ""))
    node = hardware.get("node", short)
    vendor = hardware.get("vendor", "unknown")
    product = hardware.get("product", "unknown")
    bios_ver = hardware.get("bios_version", "unknown")
    bios_date = hardware.get("bios_date", "unknown")
    cpu_model = hardware.get("cpu_model", "unknown").strip()
    cpu_cores = hardware.get("cpu_cores", 0)
    mem_gb = hardware.get("memory_gb", 0)
    disks = hardware.get("disks", [])

    checks = [
        CheckResult(category_id, category_name, f"{category_id}.hw.{short}.identity",
                    f"7.9.1 Hardware Identity: {short}", "INFO",
                    f"Vendor: {vendor}. Product: {product}. BIOS: {bios_ver} ({bios_date})", node),
        CheckResult(category_id, category_name, f"{category_id}.hw.{short}.cpu",
                    f"7.9.2 CPU: {short}", "INFO",
                    f"{cpu_model} — {cpu_cores} logical CPU(s)", node),
        CheckResult(category_id, category_name, f"{category_id}.hw.{short}.memory",
                    f"7.9.3 Memory: {short}", "INFO", f"{mem_gb} GiB RAM", node),
    ]
    if not disks:
        return checks

    disk_summary = "; ".join(
        f"{disk['name']} {disk['size']} ({disk['type']})" for disk in disks
    )

    has_rotational = any(disk.get("rotational") for disk in disks)
    disk_status = "WARNING" if has_rotational else "PASS"
    disk_note = (
        " — rotational disk detected; SSD/NVMe strongly recommended for etcd performance"
        if has_rotational else " — SSD/NVMe detected"
    )

    checks.append(
        CheckResult(category_id, category_name, f"{category_id}.hw.{short}.disk",
                    f"7.9.4 Disk: {short}", disk_status,
                    f"{disk_summary}{disk_note}", node)
    )
    return checks


def evaluate_hardware(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Dispatch evaluators for 7.9 Hardware Inventory."""
    return _evaluate_node_hardware_inventory(category_data, category_id, category_name)
