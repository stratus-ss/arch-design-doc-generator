"""Allowlisted public-contract tests for live-parity native evaluators."""
from __future__ import annotations

from hc_report.evaluators import evaluate_checks
from hc_report.evaluators.components_network import _evaluate_net_config
from hc_report.evaluators.health import _evaluate_pdb
from hc_report.evaluators.layered import evaluate_layered
from hc_report.evaluators.security import evaluate_security


def test_featuregate_default_is_pass() -> None:
    category_data = {
        "featuregate": {
            "kind": "FeatureGate",
            "metadata": {"name": "cluster"},
            "spec": {"featureSet": "Default"},
        }
    }
    checks = _evaluate_net_config(category_data, "7.3", "Components")
    featuregate = next(check for check in checks if check.check_id == "7.3.net.featuregates")
    assert featuregate.status == "PASS"


def test_featuregate_techpreview_is_fail() -> None:
    category_data = {
        "featuregate": {
            "kind": "FeatureGate",
            "metadata": {"name": "cluster"},
            "spec": {"featureSet": "TechPreviewNoUpgrade"},
        }
    }
    checks = _evaluate_net_config(category_data, "7.3", "Components")
    featuregate = next(check for check in checks if check.check_id == "7.3.net.featuregates")
    assert featuregate.status == "FAIL"
    assert featuregate.scoring_basis == "doc_backed"


def test_odf_not_found_is_not_applicable() -> None:
    category_data = {"odf_storagecluster": {"_hc_not_found": True}}
    checks = evaluate_layered(category_data, {}, "7.4", "Layered Products")
    odf_state = next(check for check in checks if check.check_id == "7.4.odf.state")
    assert odf_state.status == "NOT_APPLICABLE"


def test_odf_collection_error_is_skipped() -> None:
    category_data = {"odf_storagecluster": {"_hc_error": True}}
    checks = evaluate_layered(category_data, {}, "7.4", "Layered Products")
    odf_state = next(check for check in checks if check.check_id == "7.4.odf.state")
    assert odf_state.status == "SKIPPED"


def test_pdb_empty_list_is_info() -> None:
    checks = _evaluate_pdb({"items": []}, "7.5", "Cluster Health")
    assert checks[0].check_id == "7.5.pdb"
    assert checks[0].status == "INFO"


def test_pdb_collection_error_is_skipped() -> None:
    checks = _evaluate_pdb({"_hc_error": True}, "7.5", "Cluster Health")
    assert checks[0].status == "SKIPPED"


def test_file_integrity_not_found_is_not_applicable() -> None:
    category_data = {"fileintegrity": {"_hc_not_found": True}}
    checks = evaluate_security(category_data, {}, "7.7", "Security and Compliance")
    file_integrity = next(check for check in checks if check.check_id == "7.7.file_integrity")
    assert file_integrity.status == "NOT_APPLICABLE"


def test_ccx_cve_skipped_without_payload() -> None:
    checks = evaluate_checks({}, check_profile="core")
    cve_check = next(
        check
        for check in checks
        if check.check_id == "7.7.ccx_external.cve_2026_31431_copy_fail_in_algif_aead"
    )
    assert cve_check.status == "SKIPPED"
    assert cve_check.source == "ccx"


def test_ccx_cve_uses_payload_status() -> None:
    results = {
        "12_ccx": {
            "ccx_rules": {
                "rules": [
                    {
                        "title": "CVE-2026-31431 copy fail in algif aead",
                        "status": "FAIL",
                        "message": "kernel rule matched",
                    }
                ]
            }
        }
    }
    checks = evaluate_checks(results, check_profile="core")
    cve_check = next(
        check
        for check in checks
        if check.check_id == "7.7.ccx_external.cve_2026_31431_copy_fail_in_algif_aead"
    )
    assert cve_check.status == "FAIL"
    assert cve_check.source == "ccx"
