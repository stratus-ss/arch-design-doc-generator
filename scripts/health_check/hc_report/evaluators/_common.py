"""Shared helpers, constants, and parsing utilities for all evaluators."""
from __future__ import annotations

import re

from hc_report.models import CheckResult

# ---------------------------------------------------------------------------
# Category map (category key → (id, display name))
# ---------------------------------------------------------------------------

_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "03_base_platform":  ("7.1", "Base Platform Checks"),
    "04_topology":       ("7.2", "Topology Checks"),
    "05_components":     ("7.3", "Component Checks"),
    "06_layered":        ("7.4", "Layered Products"),
    "07_cluster_health": ("7.5", "Cluster Health"),
    "08_day2":           ("7.6", "Day-2 Operations"),
    "09_security":       ("7.7", "Security and Compliance"),
    "10_metrics":        ("7.8", "Performance Metrics"),
    "11_hardware":       ("7.9", "Hardware Inventory"),
}

# ---------------------------------------------------------------------------
# Minimum hardware requirements per OCP documentation
# ---------------------------------------------------------------------------

_MASTER_MIN_CPU = 4
_WORKER_MIN_CPU = 2
_MASTER_MIN_MEM_GIB = 16.0
_WORKER_MIN_MEM_GIB = 8.0
_MIN_DISK_GIB = 100.0
_MIN_DISK_DOCUMENTATION_URL = (
    "https://docs.openshift.com/container-platform/4.18/installing/installing_platform_agnostic/"
    "installing-platform-agnostic.html"
    "#installation-minimum-resource-requirements_installing-platform-agnostic"
)


# ---------------------------------------------------------------------------
# Generic NOT_APPLICABLE helper
# ---------------------------------------------------------------------------

def _not_applicable(
    check_id: str, description: str, category_id: str, category_name: str,
    evidence: str = "Data not collected",
) -> CheckResult:
    return CheckResult(
        category_id=category_id,
        category_name=category_name,
        check_id=check_id,
        description=description,
        status="NOT_APPLICABLE",
        evidence=evidence,
    )


def _is_missing(data: dict) -> bool:
    """Return True if data is empty, errored, or not found."""
    return not data or data.get("_hc_error") or data.get("_hc_not_found")


def _get_items(data: dict, default_single: bool = False) -> list:
    """Extract a List-kind resource's `items` array from collected data.

    Collected `oc get -o json` output is normally a List object with an
    `items` array. If `items` is absent (e.g. a single-object `oc get`
    result, or missing/empty collection data), fall back to `[data]` when
    `default_single` is True (treat `data` itself as the sole item), or
    `[]` otherwise.
    """
    if "items" in data:
        return data.get("items", [])
    return [data] if default_single else []


# ---------------------------------------------------------------------------
# Kubernetes object field accessors
# ---------------------------------------------------------------------------

def _resource_metadata(item: dict) -> dict:
    return item.get("metadata", {})


def _resource_name(item: dict, default: str = "?") -> str:
    return _resource_metadata(item).get("name", default)


def _resource_labels(item: dict) -> dict:
    return _resource_metadata(item).get("labels", {})


def _resource_annotations(item: dict) -> dict:
    return _resource_metadata(item).get("annotations", {})


def _resource_status(item: dict) -> dict:
    return item.get("status", {})


def _resource_spec(item: dict) -> dict:
    return item.get("spec", {})


def _node_info(item: dict) -> dict:
    return _resource_status(item).get("nodeInfo", {})


def _node_capacity(item: dict) -> dict:
    return _resource_status(item).get("capacity", {})


def _cluster_version_object(cluster_version_raw: dict) -> dict:
    """Return the ClusterVersion object from a List or a single-object dump."""
    cluster_version_items = _get_items(cluster_version_raw)
    if cluster_version_items:
        return cluster_version_items[0]
    if cluster_version_raw.get("kind") == "ClusterVersion":
        return cluster_version_raw
    return {}


# ---------------------------------------------------------------------------
# Resource quantity parsers
# ---------------------------------------------------------------------------

def _parse_cpu_cores(cpu_quantity: str) -> float:
    """Parse CPU string like '6' or '5500m' to float cores."""
    try:
        if str(cpu_quantity).endswith("m"):
            return float(str(cpu_quantity)[:-1]) / 1000.0
        return float(cpu_quantity)
    except (ValueError, TypeError):
        return 0.0


def _parse_quantity_gib(quantity_text: str) -> float:
    """Parse a Kubernetes quantity string (e.g. memory or ephemeral-storage) to GiB."""
    try:
        normalized = str(quantity_text)
        if normalized.endswith("Ki"):
            return int(normalized[:-2]) / (1024 ** 2)
        if normalized.endswith("Mi"):
            return int(normalized[:-2]) / 1024.0
        if normalized.endswith("Gi"):
            return float(normalized[:-2])
        if normalized.endswith("Ti"):
            return float(normalized[:-2]) * 1024.0
        return int(normalized) / (1024 ** 3)
    except (ValueError, TypeError):
        return 0.0


_LSBLK_SIZE_MULTIPLIERS_GIB = {"K": 1 / (1024 ** 2), "M": 1 / 1024.0, "G": 1.0, "T": 1024.0, "P": 1024.0 ** 2}


def _parse_lsblk_size_gib(size_text: str) -> float:
    """Parse an `lsblk SIZE` column value (e.g. '119.2G', '1T', '500M') to GiB.

    lsblk's default human-readable output uses binary (IEC) units, so a plain
    numeric value with no suffix is treated as already being in GiB.
    """
    match = re.match(r"^([\d.]+)\s*([KMGTP]?)B?$", str(size_text).strip().upper())
    if not match:
        return 0.0
    raw_value, unit = match.groups()
    try:
        value = float(raw_value)
    except ValueError:
        return 0.0
    return value * _LSBLK_SIZE_MULTIPLIERS_GIB.get(unit, 1.0)


# ---------------------------------------------------------------------------
# Condition lookup helper
# ---------------------------------------------------------------------------

def _find_condition(conditions: list, condition_type: str) -> dict:
    """Return the first condition dict matching the given type, or {} if absent."""
    return next(
        (condition for condition in conditions if condition.get("type") == condition_type),
        {},
    )


# ---------------------------------------------------------------------------
# Prometheus helper
# ---------------------------------------------------------------------------

def _parse_prometheus_vector(data: dict) -> list[dict]:
    """Extract result vector from a Prometheus instant query response."""
    if not data or data.get("_hc_error") or data.get("_hc_not_found"):
        return []
    if data.get("status") != "success":
        return []
    return data.get("data", {}).get("result", [])


def _prometheus_value(item: dict, default: float = 0.0) -> float:
    """Extract the numeric value from a Prometheus result vector item."""
    try:
        return float(item.get("value", [0, 0])[1])
    except (TypeError, ValueError, IndexError):
        return default


# ---------------------------------------------------------------------------
# Operator approval strategy (shared by base-platform 7.1.2.1 and day-2 7.6.11
# evaluators so both report identical wording/status for the same data)
# ---------------------------------------------------------------------------

def _evaluate_approval_strategy(
    subscriptions: list, category_id: str, category_name: str, check_id: str, section_title: str,
) -> CheckResult:
    """Flag subscriptions using Automatic installPlanApproval."""
    automatic_names = []
    for subscription in subscriptions:
        spec = subscription.get("spec", {})
        if spec.get("installPlanApproval") != "Automatic":
            continue
        metadata = subscription.get("metadata", {})
        automatic_names.append(metadata.get("name", "unknown"))
    if automatic_names:
        return CheckResult(
            category_id=category_id,
            category_name=category_name,
            check_id=check_id,
            description=section_title,
            status="WARNING",
            evidence=(
                f"{len(automatic_names)}/{len(subscriptions)} subscription(s) with Automatic approval: "
                f"{', '.join(automatic_names[:5])}. "
                "Manual approval recommended to prevent unplanned upgrades in production"
            ),
            resource_name="subscriptions",
        )
    return CheckResult(
        category_id=category_id,
        category_name=category_name,
        check_id=check_id,
        description=section_title,
        status="PASS",
        evidence=f"All {len(subscriptions)} subscription(s) use Manual installPlanApproval",
        resource_name="subscriptions",
    )
