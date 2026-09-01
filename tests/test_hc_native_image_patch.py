"""Allowlisted tests for native image registrySources (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.day2 import _evaluate_image_registry_sources
from hc_report.kb_loader import load_kb


def _image_config(allowed: object, blocked: object, insecure: object) -> dict:
    return {
        "spec": {
            "registrySources": {
                "allowedRegistries": allowed,
                "blockedRegistries": blocked,
                "insecureRegistries": insecure,
            }
        }
    }


def _registry_status(image_config_data: dict) -> str:
    checks = _evaluate_image_registry_sources(image_config_data, "7.6", "Day-2")
    assert checks[0].check_id == "7.6.image.registry_sources"
    return checks[0].status


def test_registry_sources_info_when_empty() -> None:
    assert _registry_status(_image_config([], [], [])) == "INFO"


def test_registry_sources_warning_when_insecure() -> None:
    assert _registry_status(_image_config([], [], ["registry.example.com"])) == "WARNING"


def test_registry_sources_fail_when_allow_and_block() -> None:
    assert _registry_status(_image_config(["a.io"], ["b.io"], [])) == "FAIL"


def test_image_alias_not_image_mgmt() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.6.tsr.6_2_3_images_patch_management")
    assert entry.content_from == "7.6.image.registry_sources"
    assert entry.include_in_findings is False
    assert entry.content_from != "7.6.image_mgmt"
