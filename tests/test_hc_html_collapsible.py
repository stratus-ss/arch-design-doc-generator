from __future__ import annotations

import re
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


def _load_html_utils():
    rendering_root = str(RENDERING_ROOT)
    if rendering_root not in sys.path:
        sys.path.insert(0, rendering_root)
    import html_utils

    return html_utils


_LEAK_HEADING_HTML = """
<html><head></head><body>
<h2>Chapter 3. Executive Summary</h2>
<p>Summary intro.</p>
<h2>P1 — CVE-2026-31431 kernel algif_aead</h2>
<p>UNIQUE_TOKEN_AFTER_P1</p>
<h2>Chapter 4. Purpose and Engagement Approach</h2>
<p>Purpose body.</p>
</body></html>
"""


def _top_level_summaries(html: str) -> list[str]:
    summaries: list[str] = []
    depth = 0
    for match in re.finditer(
        r"<details\b[^>]*>|<summary>(.*?)</summary>|</details>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        token = match.group(0).lower()
        if token.startswith("<details"):
            depth += 1
        elif token.startswith("</details"):
            depth = max(0, depth - 1)
        elif token.startswith("<summary") and depth == 1:
            summaries.append(re.sub(r"<[^>]+>", "", match.group(1)).strip())
    return summaries


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


def test_collapsify_adds_narrative_class_on_chapter_three_and_eight() -> None:
    html_collapsible = _load_html_collapsible()
    rendering_root = str(RENDERING_ROOT)
    if rendering_root not in sys.path:
        sys.path.insert(0, rendering_root)
    import html_utils

    html = """
<h2>Chapter 3. Executive Summary</h2>
<h3>3.1 Executive Summary</h3>
<p>One</p>
<p>Two</p>
<h2>Chapter 6. Observations and Recommendations</h2>
<h3>6.2 Observations</h3>
<p>Finding body</p>
<h2>Chapter 8. Conclusions</h2>
<h3>8.1 Close</h3>
<p>Close</p>
"""
    rendered = html_collapsible.collapsify(html)
    assert rendered.count(f'class="{html_utils.NARRATIVE_CHAPTER_CLASS}"') == 2
    chapter_three_open = rendered[
        rendered.rfind("<details", 0, rendered.index("<summary>Chapter 3")) :
        rendered.index("<summary>Chapter 3")
    ]
    chapter_six_open = rendered[
        rendered.rfind("<details", 0, rendered.index("<summary>Chapter 6")) :
        rendered.index("<summary>Chapter 6")
    ]
    chapter_eight_open = rendered[
        rendered.rfind("<details", 0, rendered.index("<summary>Chapter 8")) :
        rendered.index("<summary>Chapter 8")
    ]
    assert html_utils.NARRATIVE_CHAPTER_CLASS in chapter_three_open
    assert html_utils.NARRATIVE_CHAPTER_CLASS not in chapter_six_open
    assert html_utils.NARRATIVE_CHAPTER_CLASS in chapter_eight_open


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


def test_demote_priority_leak_headings_turns_p1_h2_into_h4() -> None:
    html_utils = _load_html_utils()
    rendered = html_utils.demote_priority_leak_headings(_LEAK_HEADING_HTML)
    assert "<h4>P1 — CVE-2026-31431 kernel algif_aead</h4>" in rendered
    assert "<h2>P1 — CVE-2026-31431 kernel algif_aead</h2>" not in rendered
    assert "<h2>Chapter 3. Executive Summary</h2>" in rendered
    assert "<h2>Chapter 4. Purpose and Engagement Approach</h2>" in rendered


def test_process_does_not_make_priority_h2_a_chapter_details(tmp_path: Path) -> None:
    html_collapsible = _load_html_collapsible()
    source = tmp_path / "input.html"
    target = tmp_path / "output.html"
    source.write_text(_LEAK_HEADING_HTML, encoding="utf-8")
    html_collapsible.process(source, target)
    rendered = target.read_text(encoding="utf-8")
    summaries = _top_level_summaries(rendered)
    assert any(text.startswith("Chapter 3") for text in summaries)
    assert any(text.startswith("Chapter 4") for text in summaries)
    assert not any(text.startswith("P1") for text in summaries)
    assert "<h4>P1 — CVE-2026-31431 kernel algif_aead</h4>" in rendered


def test_wrap_narrative_chapters_keeps_body_after_demoted_p1() -> None:
    html_utils = _load_html_utils()
    demoted = html_utils.demote_priority_leak_headings(_LEAK_HEADING_HTML)
    wrapped = html_utils.wrap_narrative_chapters(demoted)
    chapter_class = html_utils.NARRATIVE_CHAPTER_CLASS
    narrative_start = wrapped.index(f'class="{chapter_class}"')
    narrative_end = wrapped.index("</div>", narrative_start)
    narrative = wrapped[narrative_start:narrative_end]
    assert "UNIQUE_TOKEN_AFTER_P1" in narrative
    chapter_four = wrapped.index("Chapter 4. Purpose and Engagement Approach")
    assert chapter_four > narrative_end


def test_process_xref_script_listens_for_link_clicks(tmp_path: Path) -> None:
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
    assert "function openAnchorTarget()" in rendered
    assert "window.addEventListener('hashchange', openAnchorTarget);" in rendered
    assert "a.hc-xref-link" in rendered
    assert "addEventListener('click'" in rendered
    assert "requestAnimationFrame" in rendered
