from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RENDERING_ROOT = PROJECT_ROOT / "scripts" / "shared" / "rendering"


def _load_pdf_preprocess():
    rendering_root = str(RENDERING_ROOT)
    if rendering_root not in sys.path:
        sys.path.insert(0, rendering_root)
    import html_utils
    import pdf_preprocess

    return html_utils, pdf_preprocess


def test_wrap_narrative_chapters_marks_only_executive_summary_and_conclusions() -> None:
    html_utils, _ = _load_pdf_preprocess()
    html = """
<h2>Chapter 3. Executive Summary</h2>
<p>One</p>
<p>Two</p>
<h2>Chapter 6. Observations and Recommendations</h2>
<p>Finding body</p>
<h2>Chapter 8. Conclusions</h2>
<p>Close</p>
"""
    rendered = html_utils.wrap_narrative_chapters(html)
    assert rendered.count(f'class="{html_utils.NARRATIVE_CHAPTER_CLASS}"') == 2
    before_six = rendered[: rendered.index("<h2>Chapter 6")]
    assert before_six.rfind("</div>") > before_six.rfind("<div")
    before_three = rendered[: rendered.index("<h2>Chapter 3")]
    assert html_utils.NARRATIVE_CHAPTER_CLASS in before_three[before_three.rfind("<div") :]
    before_eight = rendered[: rendered.index("<h2>Chapter 8")]
    assert html_utils.NARRATIVE_CHAPTER_CLASS in before_eight[before_eight.rfind("<div") :]


def test_pdf_process_wraps_narrative_chapters_and_injects_css(tmp_path: Path) -> None:
    html_utils, pdf_preprocess = _load_pdf_preprocess()
    source = tmp_path / "input.html"
    target = tmp_path / "output.html"
    source.write_text(
        """<html><head></head><body>
<h2>Chapter 3. Executive Summary</h2>
<p>First</p>
<p>Second</p>
<h2>Chapter 6. Observations</h2>
<p>Finding body</p>
</body></html>""",
        encoding="utf-8",
    )
    pdf_preprocess.process(source, target)
    rendered = target.read_text(encoding="utf-8")
    assert f'<div class="{html_utils.NARRATIVE_CHAPTER_CLASS}">' in rendered
    assert ".hc-narrative-chapter p" in rendered
    assert "margin-bottom: 1em" in rendered
    six_start = rendered.index("<h2>Chapter 6")
    body_close = rendered.index("</body>")
    assert html_utils.NARRATIVE_CHAPTER_CLASS not in rendered[six_start:body_close]
