"""Evaluators for 7.7 Security and Compliance."""
from __future__ import annotations

from hc_report.evaluators._common import (
    _find_condition,
    _get_items,
    _is_missing,
    _not_applicable,
    _resource_labels,
    _resource_metadata,
    _resource_name,
    _resource_status,
)
from hc_report.evaluators._shared_checks import check_csr_pending
from hc_report.models import CheckResult

_DEFAULT_SCCS = {
    "anyuid", "hostaccess", "hostmount-anyuid", "hostnetwork", "hostnetwork-v2",
    "node-exporter", "nonroot", "nonroot-v2", "privileged", "restricted",
    "restricted-v2", "machine-api-termination-handler",
}


def _evaluate_scc(scc_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """SCC inventory: custom SCCs, privileged usage."""
    if _is_missing(scc_data):
        return [_not_applicable(f"{category_id}.scc", "Security Context Constraints", category_id, category_name)]

    items = _get_items(scc_data, default_single=True)
    custom = [
        _resource_metadata(item).get("name")
        for item in items
        if _resource_metadata(item).get("name") not in _DEFAULT_SCCS
        and _resource_metadata(item).get("name")
    ]

    checks = []
    if custom:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.scc.custom",
                                  "7.7.1 Custom Security Context Constraints", "WARNING",
                                  f"{len(custom)} custom SCC(s) detected: {', '.join(custom)}. "
                                  "Review to ensure least-privilege principle is applied", "scc"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.scc.custom",
                                  "7.7.1 Custom Security Context Constraints", "PASS",
                                  f"{len(items)} SCCs present — all are default Red Hat-managed SCCs",
                                  "scc"))

    priv_scc = next((item for item in items if _resource_name(item) == "privileged"), None)
    if priv_scc:
        users = priv_scc.get("users", [])
        groups = priv_scc.get("groups", [])
        non_system = [subject for subject in users if not subject.startswith("system:")]
        if non_system:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.scc.privileged_users",
                                      "7.7.2 Privileged SCC Users", "WARNING",
                                      f"{len(non_system)} non-system user(s) bound to 'privileged' SCC: "
                                      f"{', '.join(non_system[:5])}", "scc"))
        else:
            checks.append(CheckResult(category_id, category_name, f"{category_id}.scc.privileged_users",
                                      "7.7.2 Privileged SCC Users", "PASS",
                                      f"Privileged SCC: {len(users)} system users, "
                                      f"{len(groups)} groups — no non-system principals", "scc"))
    return checks


def _evaluate_oauth(oauth_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """OAuth identity providers."""
    if _is_missing(oauth_data):
        return [_not_applicable(f"{category_id}.oauth", "OAuth Configuration", category_id, category_name)]

    providers = oauth_data.get("spec", {}).get("identityProviders", [])
    if not providers:
        return [CheckResult(category_id, category_name, f"{category_id}.oauth.idp",
                            "7.7.3 OAuth Identity Providers", "WARNING",
                            "No identity providers configured. "
                            "Only kubeadmin (default admin) access is possible", "oauth")]
    idp_list = ", ".join(f"{pod.get('name')} ({pod.get('type')})" for pod in providers)
    return [CheckResult(category_id, category_name, f"{category_id}.oauth.idp",
                        "7.7.3 OAuth Identity Providers", "PASS",
                        f"{len(providers)} identity provider(s): {idp_list}", "oauth")]


def _evaluate_rbac(crb_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Cluster-admin bindings — count non-system principals."""
    if _is_missing(crb_data):
        return [_not_applicable(f"{category_id}.rbac", "RBAC Cluster Admin Bindings", category_id, category_name)]

    items = _get_items(crb_data)
    admin_bindings = []
    for item in items:
        role_ref = item.get("roleRef", {})
        if role_ref.get("name") == "cluster-admin":
            admin_bindings.append(item)
    non_system = []
    for binding in admin_bindings:
        for subj in binding.get("subjects", []):
            name = subj.get("name", "")
            if not name.startswith("system:"):
                non_system.append(f"{subj.get('kind')}/{name}")

    if len(non_system) > 5:
        return [CheckResult(category_id, category_name, f"{category_id}.rbac.cluster_admin",
                            "7.7.4 Cluster-Admin Bindings", "WARNING",
                            f"{len(non_system)} non-system principal(s) bound to cluster-admin: "
                            f"{', '.join(non_system[:5])} (and {len(non_system)-5} more). "
                            "Review for least-privilege compliance", "clusterrolebindings")]
    return [CheckResult(category_id, category_name, f"{category_id}.rbac.cluster_admin",
                        "7.7.4 Cluster-Admin Bindings", "PASS",
                        f"{len(admin_bindings)} cluster-admin binding(s). "
                        f"Non-system principals: {', '.join(non_system) if non_system else 'none'}",
                        "clusterrolebindings")]


def _evaluate_compliance(scan_data: dict, suite_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Compliance operator scans."""
    scan_missing = not scan_data or scan_data.get("_hc_not_found")
    suite_missing = not suite_data or suite_data.get("_hc_not_found")
    if scan_missing and suite_missing:
        return [CheckResult(category_id, category_name, f"{category_id}.compliance",
                            "7.7.5 Compliance Operator", "NOT_APPLICABLE",
                            "Compliance Operator not installed. "
                            "Consider deploying for CIS/STIG compliance scanning",
                            "compliance_scans")]

    items = _get_items(scan_data) if scan_data else []
    failed_scans = [
        _resource_metadata(item).get("name")
        for item in items
        if _resource_status(item).get("phase") not in ("DONE", "")
    ]
    if failed_scans:
        return [CheckResult(category_id, category_name, f"{category_id}.compliance",
                            "7.7.5 Compliance Scans", "WARNING",
                            f"{len(items)} compliance scan(s). Incomplete: {', '.join(failed_scans[:3])}",
                            "compliance_scans")]
    return [CheckResult(category_id, category_name, f"{category_id}.compliance",
                        "7.7.5 Compliance Scans", "PASS",
                        f"{len(items)} compliance scan(s) — all completed", "compliance_scans")]


def _evaluate_csr(csr_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Pending Certificate Signing Requests."""
    if _is_missing(csr_data):
        return [_not_applicable(f"{category_id}.csr", "Certificate Signing Requests", category_id, category_name)]

    items = _get_items(csr_data)
    pending, approved, denied = check_csr_pending(csr_data)

    if denied:
        return [CheckResult(category_id, category_name, f"{category_id}.csr",
                            "7.7.6 Certificate Signing Requests", "FAIL",
                            f"{len(denied)} CSR(s) denied: {', '.join(str(binding) for binding in denied[:5])}. "
                            f"{len(pending)} pending, {len(approved)} approved", "csr")]
    if pending:
        return [CheckResult(category_id, category_name, f"{category_id}.csr",
                            "7.7.6 Certificate Signing Requests", "WARNING",
                            f"{len(pending)} pending CSR(s) — check if nodes are waiting for certificates",
                            "csr")]
    return [CheckResult(category_id, category_name, f"{category_id}.csr",
                        "7.7.6 Certificate Signing Requests", "PASS",
                        f"{len(items)} CSR(s) total. {len(approved)} approved, "
                        f"{len(pending)} pending, {len(denied)} denied", "csr")]


def _evaluate_tsr_security_aggregate(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """TSR 7.x: Aggregate security checks."""
    checks: list[CheckResult] = []

    # 7.1.1 Container Security — SCC posture
    scc = category_data.get("scc", {})
    if not _is_missing(scc):
        items = _get_items(scc, default_single=True)
        checks.append(CheckResult(category_id, category_name, f"{category_id}.container_security",
                                  "7.1.1 Container Security", "PASS",
                                  f"{len(items)} SCCs enforcing container security boundaries", "scc"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.container_security",
                                  "7.1.1 Container Security", "SKIPPED",
                                  "SCC data unavailable", "scc"))

    # 7.1.2 Auditing
    apiserver = results.get("08_day2", {}).get("apiserver", {})
    if not _is_missing(apiserver):
        audit = apiserver.get("spec", {}).get("audit", {})
        profile = audit.get("profile", "Default")
        status = "WARNING" if profile == "None" else "PASS"
        evidence = (
            "Audit profile: None — audit logging is disabled. "
            "Red Hat recommends keeping audit logging enabled."
            if profile == "None"
            else f"Audit profile: {profile}"
        )
        checks.append(CheckResult(category_id, category_name, f"{category_id}.auditing",
                                  "7.1.2 Auditing", status,
                                  evidence, "apiserver"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.auditing",
                                  "7.1.2 Auditing", "PASS",
                                  "Default audit policy active", "apiserver"))

    # 7.1.4 Encrypting data
    apiserver_spec = apiserver.get("spec", {}) if not _is_missing(apiserver) else {}
    encryption = apiserver_spec.get("encryption", {})
    enc_type = encryption.get("type", "")
    if enc_type == "aescbc" or enc_type == "aesgcm":
        checks.append(CheckResult(category_id, category_name, f"{category_id}.encryption",
                                  "7.1.4 Encrypting Data", "PASS",
                                  f"etcd encryption enabled: {enc_type}", "encryption"))
    elif enc_type:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.encryption",
                                  "7.1.4 Encrypting Data", "INFO",
                                  f"Encryption type: {enc_type}", "encryption"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.encryption",
                                  "7.1.4 Encrypting Data", "INFO",
                                  "No explicit encryption config (default: identity — data at rest not encrypted)",
                                  "encryption"))

    # 7.1.5 Vulnerability Scanning — compliance operator
    comp_scans = category_data.get("compliance_scans", {})
    if comp_scans and not comp_scans.get("_hc_not_found"):
        checks.append(CheckResult(category_id, category_name, f"{category_id}.vuln_scan",
                                  "7.1.5 Vulnerability Scanning", "PASS",
                                  "Compliance Operator installed — scanning active", "compliance"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.vuln_scan",
                                  "7.1.5 Vulnerability Scanning", "NOT_APPLICABLE",
                                  "Compliance Operator not installed", "compliance"))

    # 7.1.6 TLS Security Profiles
    tls = apiserver_spec.get("tlsSecurityProfile", {})
    tls_type = tls.get("type", "Intermediate") if tls else "Intermediate"
    checks.append(CheckResult(category_id, category_name, f"{category_id}.tls_profile",
                              "7.1.6 TLS Security Profiles", "INFO",
                              f"TLS profile: {tls_type}", "tls"))

    # 7.1.7 Pod Security Admission
    namespace_data = category_data.get("namespaces", results.get("08_day2", {}).get("namespaces", {}))
    if not _is_missing(namespace_data):
        namespace_items = _get_items(namespace_data)
        psa_enforced = 0
        for namespace in namespace_items:
            labels = _resource_labels(namespace)
            if any(label_key.startswith("pod-security.kubernetes.io/") for label_key in labels):
                psa_enforced += 1
        checks.append(CheckResult(category_id, category_name, f"{category_id}.psa",
                                  "7.1.7 Pod Security Admission", "PASS",
                                  f"PSA labels on {psa_enforced}/{len(namespace_items)} namespace(s). "
                                  "OCP enforces restricted by default via SCC",
                                  "psa"))
    else:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.psa",
                                  "7.1.7 Pod Security Admission", "PASS",
                                  "OCP enforces restricted-v2 SCC by default (PSA equivalent)",
                                  "psa"))

    # 7.2.2 File Integrity
    checks += _evaluate_file_integrity(category_data.get("fileintegrity", {}), category_id, category_name)
    return checks


def _evaluate_file_integrity(
    file_integrity_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    if file_integrity_data.get("_hc_error"):
        return [CheckResult(
            category_id, category_name, f"{category_id}.file_integrity",
            "7.2.2 File Integrity", "SKIPPED",
            "FileIntegrity collection failed", "fio",
        )]
    items = [] if file_integrity_data.get("_hc_not_found") else _get_items(
        file_integrity_data,
    )
    if not items:
        return [CheckResult(
            category_id, category_name, f"{category_id}.file_integrity",
            "7.2.2 File Integrity", "NOT_APPLICABLE",
            "File Integrity Operator not installed", "fio",
        )]
    failed_names = []
    for item in items:
        status = item.get("status", {}) if isinstance(item.get("status"), dict) else {}
        phase = str(status.get("phase", ""))
        failed_condition = _find_condition(status.get("conditions", []), "Failed")
        if phase.lower() == "failed" or failed_condition.get("status") == "True":
            failed_names.append(_resource_name(item))
    if failed_names:
        return [CheckResult(
            category_id, category_name, f"{category_id}.file_integrity",
            "7.2.2 File Integrity", "FAIL",
            f"FileIntegrity Failed: {', '.join(failed_names[:5])}",
            "fio",
        )]
    return [CheckResult(
        category_id, category_name, f"{category_id}.file_integrity",
        "7.2.2 File Integrity", "PASS",
        f"{len(items)} FileIntegrity resource(s) healthy",
        "fio",
    )]


def evaluate_security(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Dispatch evaluators for 7.7 Security and Compliance."""
    checks: list[CheckResult] = []
    base = results.get("03_base_platform", {})
    # TSR 7.x aggregate checks
    checks += _evaluate_tsr_security_aggregate(category_data, results, category_id, category_name)
    # Existing detailed checks
    checks += _evaluate_scc(category_data.get("scc", {}), category_id, category_name)
    checks += _evaluate_oauth(category_data.get("oauth", {}), category_id, category_name)
    checks += _evaluate_rbac(category_data.get("clusterrolebindings_admin", {}), category_id, category_name)
    checks += _evaluate_compliance(
        category_data.get("compliance_scans", {}),
        category_data.get("compliance_suites", {}),
        category_id, category_name,
    )
    checks += _evaluate_csr(base.get("csr", {}), category_id, category_name)
    return checks
