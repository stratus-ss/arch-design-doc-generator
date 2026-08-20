from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RENDERING_ROOT = PROJECT_ROOT / "scripts" / "shared" / "rendering"


def _load_html_collapsible():
    rendering_root = str(RENDERING_ROOT)
    if rendering_root not in sys.path:
        sys.path.insert(0, rendering_root)
    import html_collapsible

    return html_collapsible


def test_inject_crosslinks_adds_forward_and_back_links() -> None:
    html_collapsible = _load_html_collapsible()
    html = """
<html><head></head><body>
<p><span id="finding-6-2-2-3" data-check-id="7.3.etcd.log_errors" data-evidence-id="evidence-7-3-etcd-log-errors"></span></p>
<p><span id="evidence-7-3-etcd-log-errors" data-check-id="7.3.etcd.log_errors" data-finding-ids="finding-6-2-2-3,finding-6-2-2-9"></span></p>
</body></html>
"""
    rendered = html_collapsible._inject_crosslinks(html)
    assert 'href="#evidence-7-3-etcd-log-errors">View evidence<' in rendered
    assert 'href="#finding-6-2-2-3">See finding 6.2.2.3<' in rendered
    assert 'href="#finding-6-2-2-9">See finding 6.2.2.9<' in rendered


def test_inject_crosslinks_leaves_unpaired_anchors_unchanged() -> None:
    html_collapsible = _load_html_collapsible()
    html = """
<html><head></head><body>
<p><span id="finding-6-2-2-3"></span></p>
<p><span id="evidence-7-3-etcd-log-errors"></span></p>
</body></html>
"""
    rendered = html_collapsible._inject_crosslinks(html)
    assert rendered == html


def test_process_injects_links_styles_and_anchor_open_script(tmp_path: Path) -> None:
    html_collapsible = _load_html_collapsible()
    source = tmp_path / "input.html"
    target = tmp_path / "output.html"
    source.write_text(
        """<html><head></head><body>
<h2>Chapter 6. Observations and Recommendations</h2>
<h3>6.2 Observations and Recommendations by Priority</h3>
<h4>6.2.2.3 ETCD Log Errors</h4>
<p>Observation body</p>
<p><span id="finding-6-2-2-3" data-evidence-id="evidence-7-3-etcd-log-errors"></span></p>
<h2>Chapter 7. Raw Check Report</h2>
<p><span id="evidence-7-3-etcd-log-errors" data-finding-ids="finding-6-2-2-3"></span></p>
<table><tbody><tr><td>Check</td><td>ETCD Log Errors</td></tr></tbody></table>
</body></html>""",
        encoding="utf-8",
    )

    html_collapsible.process(source, target)
    rendered = target.read_text(encoding="utf-8")

    assert "<details" in rendered
    assert "<h4" in rendered
    assert "<table" in rendered
    assert "hc-xref-link" in rendered
    assert 'href="#evidence-7-3-etcd-log-errors"' in rendered
    assert 'href="#finding-6-2-2-3"' in rendered
    assert rendered.index("<h4") < rendered.index('href="#evidence-7-3-etcd-log-errors"')
    assert rendered.index('href="#finding-6-2-2-3"') < rendered.index("<table")
    assert "function openAnchorTarget()" in rendered
    assert "window.addEventListener('hashchange', openAnchorTarget);" in rendered


def test_inject_colgroups_cover_meta_uses_wider_label_column() -> None:
    rendering_root = str(RENDERING_ROOT)
    if rendering_root not in sys.path:
        sys.path.insert(0, rendering_root)
    import html_utils

    html = """
<div class="cover-meta"><table><tr><th>Customer</th><td>Acme</td></tr></table></div>
<table><tr><th>Check</th><td>Value</td></tr></table>
"""
    rendered = html_utils.inject_colgroups(html)
    cover_meta_start = rendered.index('class="cover-meta"')
    cover_meta_end = rendered.index("</div>", cover_meta_start)
    cover_meta = rendered[cover_meta_start:cover_meta_end]
    other_table = rendered[cover_meta_end:]
    assert "width:42%" in cover_meta
    assert "width:58%" in cover_meta
    assert "width:18%" in other_table
    assert "width:82%" in other_table
