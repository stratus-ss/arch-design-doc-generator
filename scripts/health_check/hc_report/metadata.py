"""Derive cluster metadata from collected results, falling back to project config."""
from __future__ import annotations

import re
from datetime import date


def _cfg_val(hc: dict, key: str) -> str:
    v = hc.get(key, "")
    return str(v).strip() if v else "TBD"


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
        return "".join(w[0] for w in words if w[0].isalpha()).upper()
    return re.sub(r"[^A-Za-z0-9]", "", words[0]).upper() if words else "CLIENT"


def _derive_from_clusterversion(cv_data: dict, meta: dict) -> None:
    """Update OCP version/channel from ClusterVersion if still TBD.

    Does not set cluster_name — ClusterVersion.metadata.name is always
    ``version`` on OpenShift and is not a cluster identifier.
    """
    if not cv_data or cv_data.get("_hc_error") or cv_data.get("_hc_not_found"):
        return
    cv_spec = cv_data.get("spec", {})
    cv_status = cv_data.get("status", {})
    history = cv_status.get("history", [])
    desired = cv_status.get("desired", {})

    if meta["ocp_version"] == "TBD":
        meta["ocp_version"] = (
            desired.get("version")
            or (history[0].get("version") if history else None)
            or "TBD"
        )
    if meta["channel"] == "TBD":
        meta["channel"] = cv_spec.get("channel") or "TBD"


def _derive_from_infrastructure(infra_data: dict, meta: dict) -> None:
    """Update meta fields from Infrastructure if still TBD."""
    if not infra_data or infra_data.get("_hc_error") or infra_data.get("_hc_not_found"):
        return
    infra_status = infra_data.get("status", {})
    if _is_placeholder_cluster_name(meta["cluster_name"]):
        meta["cluster_name"] = infra_status.get("infrastructureName") or "TBD"
    if meta["install_type"] != "TBD":
        return
    plat = infra_data.get("spec", {}).get("platformSpec", {})
    if not plat:
        return
    ptype = list(plat.keys())[0]
    plat_status = infra_status.get("platformStatus", {})
    pdetails = plat_status.get(ptype.lower(), {}) or plat_status.get(ptype, {})
    if pdetails.get("apiServerInternalIP") or pdetails.get("apiServerInternalIPs"):
        meta["install_type"] = f"IPI ({ptype})"
    else:
        meta["install_type"] = f"UPI ({ptype})"


def _extract_cv_data(base: dict) -> dict:
    cv_raw = base.get("clusterversion", {})
    cv_items = (
        cv_raw.get("items", [])
        if cv_raw.get("kind") == "List" or "items" in cv_raw
        else []
    )
    return cv_items[0] if cv_items else (
        cv_raw if cv_raw.get("kind") == "ClusterVersion" else {}
    )


def derive_metadata(results: dict, config: dict) -> dict:
    """Extract cluster metadata, falling back to config for missing fields."""
    hc = config.get("health_check", {})
    client_name = config.get("client_name", "TBD").replace("{CLIENT}", "TBD")

    meta = {
        "client_name":   client_name,
        "client_prefix": _build_client_initials_prefix(client_name),
        "cluster_name":  _cfg_val(hc, "cluster_name"),
        "ocp_version":   _cfg_val(hc, "ocp_version"),
        "case_number":   _cfg_val(hc, "case_number"),
        "author":        _cfg_val(hc, "author"),
        "channel":       _cfg_val(hc, "channel"),
        "install_type":  _cfg_val(hc, "install_type"),
        "report_date":   (
            _cfg_val(hc, "report_date")
            if _cfg_val(hc, "report_date") != "TBD"
            else date.today().strftime("%B %Y")
        ),
        "capture_date":  _cfg_val(hc, "capture_date"),
    }

    base = results.get("03_base_platform", {})
    _derive_from_clusterversion(_extract_cv_data(base), meta)
    _derive_from_infrastructure(base.get("infrastructure", {}), meta)

    manifest = results.get("_manifest", {})
    if meta["capture_date"] == "TBD":
        ts = manifest.get("timestamp", "")
        if ts:
            meta["capture_date"] = ts[:10]

    return meta
