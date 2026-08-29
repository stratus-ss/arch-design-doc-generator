"""Allowlisted tests for the Chapter 6 parity scorecard classifier."""

import importlib.util
import json
from pathlib import Path

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hc_meta_scorecard_sample.json"
SCORECARD_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "tmp"
    / "hc_tsr_live_parity_meta"
    / "build_chapter6_scorecard.py"
)

_spec = importlib.util.spec_from_file_location("scorecard_module", SCORECARD_SCRIPT)
scorecard_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scorecard_module)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_ccx_internal_is_unreachable():
    fixture = _load_fixture()
    rules = fixture["rules"]
    live_ids = set(fixture["live_ids"])
    status = scorecard_module.classify_orig_finding(
        "7.7.ccx_internal.tls_handshake_errors", live_ids, rules, None
    )
    assert status == "unreachable"


def test_exact_live_id_is_covered():
    fixture = _load_fixture()
    rules = fixture["rules"]
    live_ids = set(fixture["live_ids"])
    status = scorecard_module.classify_orig_finding(
        "7.3.monitoring.config", live_ids, rules, None
    )
    assert status == "covered"


def test_missing_reachable_is_need_scorer():
    fixture = _load_fixture()
    rules = fixture["rules"]
    live_ids = set(fixture["live_ids"])
    status = scorecard_module.classify_orig_finding(
        "7.3.tsr.3_5_5_etcd_compaction", live_ids, rules, None
    )
    assert status == "need_scorer"
