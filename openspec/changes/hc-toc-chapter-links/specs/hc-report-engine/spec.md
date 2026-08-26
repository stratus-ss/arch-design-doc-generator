# Health Check Report Engine (delta)

## ADDED Requirements

### Requirement: Chapter 2 TOC is in-document links
HTML and PDF export SHALL turn Chapter 2 numbered chapter lines into fragment links (`a.hc-toc-link`) whose `href` matches the corresponding report-chapter `h2` `id`. Numbered steps outside Chapter 2 SHALL stay unlinked. HTML SHALL open ancestor `<details>` when a TOC link is activated.

#### Scenario: TOC lines link to chapter heading ids
- GIVEN pandoc HTML with Chapter 1–3 headings that have `id`s, a Chapter 2 body of `1. Introduction<br />2. Table of Contents<br />3. Executive Summary`, and a later `1. Confirm…` paragraph
- WHEN `linkify_chapter_toc` runs (HTML `process` and PDF `process`)
- THEN the Chapter 2 Introduction and Executive Summary lines are `a.hc-toc-link` pointing at those heading ids
- AND the later `1. Confirm` line is not a TOC link

#### Scenario: HTML TOC click opens collapsed chapters
- GIVEN exported HTML from `html_collapsible.process`
- WHEN the user activates `a.hc-toc-link`
- THEN ancestor `<details>` are opened and the heading target is scrolled into view (script: click on `a.hc-xref-link, a.hc-toc-link` plus existing hashchange)
