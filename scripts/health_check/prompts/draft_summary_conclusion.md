You are drafting customer-facing sections of a Red Hat OpenShift Health Check report for a consultant to paste after a human review.

## Input

The block below is P0–P3 finding **descriptions** and check IDs from Chapter 6.2. It is generic knowledge-base prose, not cluster evidence.

- Do **not** invent hostnames, node names, case numbers, cluster names, or metrics that are not in the dump.
- Do **not** read Observation, Recommendation, Chapter 7, or the source report file.
- If a name is required, write "the assessed cluster".
- Do not ask for more files.

{{FINDING_DUMP}}

## Output rules

Your entire reply must be markdown with **exactly** these headings, in this order, and nothing else (no preamble, no code fence around the whole reply):

## Chapter 3. Executive Summary

### 3.1 Executive Summary

A concise overview (2 paragraphs maximum) written for C-level and management readers. State the overall cluster posture, the count of findings by severity, and the primary business risk if P0/P1 items are left unresolved. Write in plain business language. Do NOT include check IDs, CVE numbers, component names, or any technical detail.

### 3.2 Technical Summary

Grouped risk themes (2–4 short paragraphs) covering control-plane health, observability, security and patching, and operational hygiene — with specific check IDs, CVE numbers, and affected component names where relevant. Prioritize P0, then P1, then recurring P2 themes. Do not list every P3.

Then a **Priority Remediation List** as a bulleted list of every P0 and P1, plus material P2 themes, each formatted as:
- **P{n}** — {one-line title} (`{check_id}`)

## Chapter 8. Conclusions

1. A short wrap-up of what should be remediated first (P0/P1 themes, then material P2).
2. Then include **all** of these points:
   - This assessment reflects configuration and operational state at a single point in time; cluster state may have changed since data was captured.
   - Sizing, capacity planning, and performance benchmarking are outside the scope of this engagement.
   - Remediation timelines should be prioritized according to the P0–P3 classification: P0 findings require immediate attention, P1 findings should be addressed within the current sprint or change window.
   - Red Hat recommends scheduling a follow-up review after P0 and P1 remediations are completed to confirm resolution.
