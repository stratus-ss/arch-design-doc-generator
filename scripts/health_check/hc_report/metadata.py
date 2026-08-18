"""Derive cluster metadata from collected results, falling back to project config."""
from __future__ import annotations

import re
from datetime import date


def _config_value(health_check: dict, key: str) -> str:
    value = health_check.get(key, "")
    return str(value).strip() if value else "TBD"


def _is_placeholder_cluster_name(name: str) -> bool:
    """True when cluster_name still needs derivation.

    OpenShift's ClusterVersion object is always named ``version``; treat that
    literal as a placeholder, not a real cluster name.
    """
    return name in ("", "TBD", "version")


def _build_client_initials_prefix(client_name: str) -> str:
    """Derive the Health Check report filename prefix from a client name (initials, e.g. 'Example Client' -> 'EC')."""
    words = client_name.split()
    if len(words) > 1:
        return "".join(word[0] for word in words if word[0].isalpha()).upper()
    return re.sub(r"[^A-Za-z0-9]", "", words[0]).upper() if words else "CLIENT"


def _derive_from_clusterversion(cluster_version_data: dict, metadata: dict) -> None:
    """Update OCP version/channel from ClusterVersion if still TBD.

    Does not set cluster_name — ClusterVersion.metadata.name is always
    ``version`` on OpenShift and is not a cluster identifier.
    """
    if (
        not cluster_version_data
        or cluster_version_data.get("_hc_error")
        or cluster_version_data.get("_hc_not_found")
    ):
        return
    cluster_version_spec = cluster_version_data.get("spec", {})
    cluster_version_status = cluster_version_data.get("status", {})
    history = cluster_version_status.get("history", [])
    desired = cluster_version_status.get("desired", {})

    if metadata["ocp_version"] == "TBD":
        metadata["ocp_version"] = (
            desired.get("version")
            or (history[0].get("version") if history else None)
            or "TBD"
        )
    if metadata["channel"] == "TBD":
        metadata["channel"] = cluster_version_spec.get("channel") or "TBD"


def _derive_from_infrastructure(infra_data: dict, metadata: dict) -> None:
    """Update metadata fields from Infrastructure if still TBD."""
    if not infra_data or infra_data.get("_hc_error") or infra_data.get("_hc_not_found"):
        return
    infra_status = infra_data.get("status", {})
    if _is_placeholder_cluster_name(metadata["cluster_name"]):
        metadata["cluster_name"] = infra_status.get("infrastructureName") or "TBD"
    if metadata["install_type"] != "TBD":
        return
    platform_spec = infra_data.get("spec", {}).get("platformSpec", {})
    if not platform_spec:
        return
    platform_type = list(platform_spec.keys())[0]
    platform_status = infra_status.get("platformStatus", {})
    platform_details = (
        platform_status.get(platform_type.lower(), {})
        or platform_status.get(platform_type, {})
    )
    if platform_details.get("apiServerInternalIP") or platform_details.get("apiServerInternalIPs"):
        metadata["install_type"] = f"IPI ({platform_type})"
    else:
        metadata["install_type"] = f"UPI ({platform_type})"


def _extract_cluster_version_data(base: dict) -> dict:
    cluster_version_raw = base.get("clusterversion", {})
    cluster_version_items = (
        cluster_version_raw.get("items", [])
        if cluster_version_raw.get("kind") == "List" or "items" in cluster_version_raw
        else []
    )
    return cluster_version_items[0] if cluster_version_items else (
        cluster_version_raw if cluster_version_raw.get("kind") == "ClusterVersion" else {}
    )


def derive_metadata(results: dict, config: dict) -> dict:
    """Extract cluster metadata, falling back to config for missing fields."""
    health_check = config.get("health_check", {})
    client_name = config.get("client_name", "TBD").replace("{CLIENT}", "TBD")

    metadata = {
        "client_name":   client_name,
        "client_prefix": _build_client_initials_prefix(client_name),
        "cluster_name":  _config_value(health_check, "cluster_name"),
        "ocp_version":   _config_value(health_check, "ocp_version"),
        "case_number":   _config_value(health_check, "case_number"),
        "author":        _config_value(health_check, "author"),
        "channel":       _config_value(health_check, "channel"),
        "install_type":  _config_value(health_check, "install_type"),
        "report_date":   (
            _config_value(health_check, "report_date")
            if _config_value(health_check, "report_date") != "TBD"
            else date.today().strftime("%B %Y")
        ),
        "capture_date":  _config_value(health_check, "capture_date"),
    }

    base = results.get("03_base_platform", {})
    _derive_from_clusterversion(_extract_cluster_version_data(base), metadata)
    _derive_from_infrastructure(base.get("infrastructure", {}), metadata)

    manifest = results.get("_manifest", {})
    if metadata["capture_date"] == "TBD":
        timestamp = manifest.get("timestamp", "")
        if timestamp:
            metadata["capture_date"] = timestamp[:10]

    return metadata
