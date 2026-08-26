# Design: hc-toc-chapter-links

`html_utils.linkify_chapter_toc` maps report-chapter `h2` ids by chapter number, then rewrites numbered lines only in the Chapter 2 body. `html_collapsible.process` and `pdf_preprocess.process` both call it after demote. HTML click handling uses `a.hc-xref-link, a.hc-toc-link`. Template chapter headings are not given `{#id}` so `draft_summary_conclusion.py` heading splits stay valid.
