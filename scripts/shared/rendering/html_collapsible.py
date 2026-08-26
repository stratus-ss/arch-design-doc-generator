#!/usr/bin/env python3
"""
Post-process pandoc HTML output to wrap Chapter (h2) and Section (h3) headings
in <details>/<summary> for collapsible navigation.

Usage:
    python3 html_collapsible.py input.html output.html [--open-chapters]

Options:
    --open-chapters     Leave h2 (Chapter) sections open by default; only h3 collapsed
"""
import argparse
import re
from pathlib import Path

from html_utils import (
    NARRATIVE_CHAPTER_CLASS,
    NARRATIVE_PARAGRAPH_CSS,
    demote_priority_leak_headings,
    inject_colgroups,
    is_narrative_chapter_heading,
    is_report_chapter_heading,
    linkify_chapter_toc,
)

_FINDING_SPAN_RE = re.compile(
    r'(<span\b[^>]*\bid="finding-[^"]+"[^>]*></span>)',
    re.IGNORECASE,
)
_EVIDENCE_SPAN_RE = re.compile(
    r'(<span\b[^>]*\bid="evidence-[^"]+"[^>]*></span>)',
    re.IGNORECASE,
)


def _get_attr(fragment: str, attr: str) -> str:
    match = re.search(rf'\b{re.escape(attr)}="([^"]+)"', fragment)
    if not match:
        return ""
    return match.group(1)


def _display_finding_label(anchor_id: str) -> str:
    finding_id = anchor_id.removeprefix("finding-").replace("-", ".")
    return f"See finding {finding_id}"


def _build_link(href: str, label: str, variant: str) -> str:
    return f'<a class="hc-xref-link {variant}" href="#{href}">{label}</a>'


def _replace_finding_anchor(match: re.Match[str]) -> str:
    span_html = match.group(1)
    target_id = _get_attr(span_html, "data-evidence-id")
    if not target_id:
        return span_html
    link = _build_link(target_id, "View evidence", "hc-xref-forward")
    return span_html + link


def _replace_evidence_anchor(match: re.Match[str]) -> str:
    span_html = match.group(1)
    finding_ids = _get_attr(span_html, "data-finding-ids")
    if not finding_ids:
        return span_html
    links = []
    for finding_id in finding_ids.split(","):
        clean_id = finding_id.strip()
        if not clean_id:
            continue
        links.append(_build_link(clean_id, _display_finding_label(clean_id), "hc-xref-back"))
    if not links:
        return span_html
    return span_html + '<span class="hc-xref-group">' + " ".join(links) + "</span>"


def _inject_crosslinks(html: str) -> str:
    """Inject HTML-only navigation links next to finding and evidence anchors."""
    html = _FINDING_SPAN_RE.sub(_replace_finding_anchor, html)
    return _EVIDENCE_SPAN_RE.sub(_replace_evidence_anchor, html)


def _inject_anchor_open_js(html: str) -> str:
    """Open ancestor <details> blocks when navigating to an anchor target."""
    script = """
<script>
function openAnchorTarget() {
  if (!window.location.hash) { return; }
  const target = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
  if (!target) { return; }
  let node = target.parentElement;
  while (node) {
    if (node.tagName === 'DETAILS') {
      node.open = true;
    }
    node = node.parentElement;
  }
  window.requestAnimationFrame(function () {
    target.scrollIntoView({ block: 'start' });
  });
}
document.addEventListener('click', function (event) {
  const link = event.target.closest('a.hc-xref-link, a.hc-toc-link');
  if (!link) { return; }
  const href = link.getAttribute('href') || '';
  if (href.charAt(0) !== '#' || href.length < 2) { return; }
  event.preventDefault();
  if (window.location.hash !== href) {
    window.location.hash = href;
  } else {
    openAnchorTarget();
  }
});
window.addEventListener('hashchange', openAnchorTarget);
window.addEventListener('DOMContentLoaded', function () {
  window.setTimeout(openAnchorTarget, 0);
});
</script>
"""
    return html.replace("</head>", script + "\n</head>", 1)


def _split_sections(html: str, tag: str) -> list[tuple[str, str]]:
    """
    Split HTML into sections at each <tag ...> boundary.
    Returns list of (heading_html, body_html) tuples.
    The first entry has an empty heading (content before the first tag).
    """
    pattern = re.compile(
        rf'(<{tag}(?:\s[^>]*)?>.*?</{tag}>)',
        re.IGNORECASE | re.DOTALL,
    )
    parts = pattern.split(html)
    # parts = [preamble, heading1, body1, heading2, body2, ...]
    sections = []
    sections.append(("", parts[0]))  # content before first heading
    for index in range(1, len(parts), 2):
        heading = parts[index]
        body = parts[index + 1] if index + 1 < len(parts) else ""
        sections.append((heading, body))
    return sections


def _merge_non_chapter_h2_sections(
    sections: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Keep only Chapter N h2s as split points; append other h2s to the prior body."""
    merged: list[tuple[str, str]] = [sections[0]]
    for heading_html, body_html in sections[1:]:
        if is_report_chapter_heading(heading_html):
            merged.append((heading_html, body_html))
            continue
        last_heading, last_body = merged[-1]
        merged[-1] = (last_heading, last_body + heading_html + body_html)
    return merged


def _heading_text(heading_html: str) -> str:
    """Strip tags to get plain text for the summary element."""
    return re.sub(r'<[^>]+>', '', heading_html).strip()


def _wrap_in_details(
    heading_html: str,
    body_html: str,
    open_by_default: bool,
    extra_class: str = "",
) -> str:
    text = _heading_text(heading_html)
    open_attr = " open" if open_by_default else ""
    class_attr = f' class="{extra_class}"' if extra_class else ""
    return (
        f'<details{open_attr}{class_attr}>\n'
        f'<summary>{text}</summary>\n'
        f'{heading_html}\n'
        f'{body_html}'
        f'</details>\n'
    )


def collapsify(html: str, open_chapters: bool = False) -> str:
    """
    1. Split at h2 (Chapters). Each Chapter is a <details>.
       open_chapters=True means Chapters are expanded by default.
    2. Within each Chapter body, split at h3 (Sections). Each Section is
       a nested <details>, collapsed by default.
    """
    # ---- Step 1: wrap h2 chapters ----------------------------------------
    ch_sections = _merge_non_chapter_h2_sections(_split_sections(html, "h2"))
    chapter_blocks = []

    preamble_heading, preamble_body = ch_sections[0]
    chapter_blocks.append(preamble_body)

    for heading_html, body_html in ch_sections[1:]:
        # ---- Step 2: wrap h3 sections inside each chapter body -------------
        sec_sections = _split_sections(body_html, "h3")
        inner_parts = [sec_sections[0][1]]  # content before first h3

        for sec_heading, sec_body in sec_sections[1:]:
            inner_parts.append(
                _wrap_in_details(sec_heading, sec_body, open_by_default=False)
            )

        wrapped_body = "".join(inner_parts)
        narrative_class = (
            NARRATIVE_CHAPTER_CLASS if is_narrative_chapter_heading(heading_html) else ""
        )
        chapter_blocks.append(
            _wrap_in_details(
                heading_html,
                wrapped_body,
                open_by_default=open_chapters,
                extra_class=narrative_class,
            )
        )

    return "".join(chapter_blocks)


def _inject_collapsible_css(html: str) -> str:
    """Inject CSS for <details>/<summary> styling before </head>."""
    css = """
<style>
/* ── Collapsible section chrome ─────────────────────────────────────── */
details {
  margin: 0 0 6px 0;
}
details > summary {
  cursor: pointer;
  list-style: none;
  padding: 6px 10px;
  border-radius: 4px;
  font-weight: 600;
  user-select: none;
  background: #f1f5f9;
  border-left: 3px solid var(--primary, #be0000);
  display: flex;
  align-items: center;
  gap: 8px;
}
details > summary::-webkit-details-marker { display: none; }
details > summary::before {
  content: "▶";
  font-size: 0.7em;
  transition: transform 0.2s;
  flex-shrink: 0;
}
details[open] > summary::before {
  transform: rotate(90deg);
}
details > summary:hover {
  background: #e2e8f0;
}
/* Hide the duplicate heading rendered inside the details body */
details > h2,
details > h3 {
  margin-top: 4px;
}
/* Indent nested (h3) details */
details details {
  margin-left: 12px;
}
details details > summary {
  background: #f8fafc;
  border-left: 2px solid var(--secondary, #1155cc);
  font-size: 0.95em;
}
/* Global expand/collapse controls */
#hc-controls {
  position: sticky;
  top: 0;
  z-index: 100;
  background: white;
  padding: 8px 16px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  gap: 8px;
  align-items: center;
}
#hc-controls button {
  padding: 4px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  background: #f1f5f9;
  cursor: pointer;
  font-size: 0.85em;
}
#hc-controls button:hover { background: #e2e8f0; }
#hc-controls .label {
  font-size: 0.8em;
  color: #64748b;
  margin-left: auto;
}
.hc-xref-link {
  display: inline-block;
  margin: 0.25rem 0.5rem 0.25rem 0;
  font-size: 0.85em;
  color: var(--secondary, #1155cc);
  text-decoration: none;
}
.hc-xref-link:hover {
  text-decoration: underline;
}
.hc-toc-link {
  text-decoration: underline;
}
h2[id], h3[id] {
  scroll-margin-top: 3rem;
}
.hc-xref-group {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-left: 0.25rem;
}
[id^="finding-"], [id^="evidence-"] {
  scroll-margin-top: 3rem;
}
""" + NARRATIVE_PARAGRAPH_CSS + """
</style>
<script>
function expandAll()  { document.querySelectorAll('details').forEach(d => d.open = true);  }
function collapseAll(){ document.querySelectorAll('details').forEach(d => d.open = false); }
</script>
"""
    return html.replace("</head>", css + "\n</head>", 1)


def _inject_controls_bar(html: str) -> str:
    """Insert expand/collapse toolbar after <body>."""
    bar = (
        '\n<div id="hc-controls">'
        '<button onclick="expandAll()">Expand all</button>'
        '<button onclick="collapseAll()">Collapse all</button>'
        '<span class="label">OpenShift Health Check Report</span>'
        '</div>\n'
    )
    return re.sub(r'(<body[^>]*>)', r'\1' + bar, html, count=1, flags=re.IGNORECASE)


def process(source_path: Path, destination_path: Path, open_chapters: bool = False) -> None:
    html = source_path.read_text(encoding="utf-8")

    # Extract <body> content, transform it, put it back
    body_match = re.search(r'(<body[^>]*>)(.*)(</body>)', html, re.DOTALL | re.IGNORECASE)
    if body_match:
        html_before_body = html[:body_match.start(2)]
        body = body_match.group(2)
        html_after_body = html[body_match.end(2):]
        body = demote_priority_leak_headings(body)
        body = linkify_chapter_toc(body)
        body = collapsify(body, open_chapters=open_chapters)
        html = html_before_body + body + html_after_body
    else:
        html = demote_priority_leak_headings(html)
        html = linkify_chapter_toc(html)
        html = collapsify(html, open_chapters=open_chapters)

    html = _inject_crosslinks(html)
    html = inject_colgroups(html)
    html = _inject_collapsible_css(html)
    html = _inject_anchor_open_js(html)
    html = _inject_controls_bar(html)

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(html, encoding="utf-8")
    print(f"  ✓ {destination_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Make HC report HTML collapsible")
    parser.add_argument("input",  type=Path, help="Input HTML file (from pandoc)")
    parser.add_argument("output", type=Path, help="Output HTML file")
    parser.add_argument("--open-chapters", action="store_true",
                        help="Leave Chapter sections expanded by default")
    args = parser.parse_args()
    process(args.input, args.output, open_chapters=args.open_chapters)


if __name__ == "__main__":
    main()
