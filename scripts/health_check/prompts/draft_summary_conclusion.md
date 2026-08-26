You are drafting customer-facing sections of a Red Hat OpenShift Health Check report for a consultant to paste after a human review.

This is pass 1 of 3. You write Chapter 3 and Chapter 8 sections 8.1–8.3 only. Later passes append 8.4 and 8.5. Do not write 8.4, 8.5, or the engagement-bound disclaimer bullets.

## Input

The block below starts with **full-report counts** for P0–P3. Description bodies, Chapter 6.2 headings, and Level of Impact lines are **P0–P1 only**. P2 and P3 item names are intentionally absent. Do not claim P2 or P3 findings were not raised when those counts are greater than zero.

- Do **not** invent hostnames, node names, case numbers, cluster names, or metrics that are not in the dump.
- Do **not** read Observation, Recommendation, Chapter 7, or the source report file.
- If a name is required, write "the assessed cluster".
- Do not ask for more files.
- Do **not** use internal check IDs (values like `7.5.pods.crashloop`).

{{FINDING_DUMP}}

## Tone

Write in conservative, measured language. Avoid hyperbole and alarmist verbs (for example: destabilise, catastrophic, critical failure, undermine, collapse). Do not invent downstream effects on other subsystems. Prefer "may" and "can" over predictions of outage or business harm that are not in the dump. Spell out operational impact from the dump (including cost of doing nothing). Overlap with other sections is acceptable.

## Output rules

Your entire reply must be markdown with **exactly** these headings, in this order, and nothing else (no preamble, no code fence around the whole reply):

## Chapter 3. Executive Summary

### 3.1 Executive Summary

Audience: C-level and management. Completeness over brevity. Write **three to five paragraphs** in plain business language.

Cover all of the following:
- Overall cluster posture and the count of **P0, P1, P2, and P3** findings from the Counts line. Never state that P2 or P3 findings were not raised when those counts are greater than zero.
- That P2 and P3 items are usually the majority; they are documented in Chapter 6 and will be grouped as remaining work in 8.4.
- The main P0/P1 themes in operational terms so a non-engineer understands what was found.
- Why those themes matter, and the cost of leaving P0/P1 unresolved, using only significance in the dump. Do not predict financial or reputational harm.
- That P0 and P1 items should be addressed first.

Do NOT include check IDs, CVE numbers, hostnames, or low-level configuration keys. High-level capability names are allowed (for example: etcd, logging, machine configuration).

### 3.2 Technical Summary

Audience: platform engineers and architects. Write connected **theme narrative** (typically 4–8 paragraphs). The dump is background; it is not an outline of headings to reproduce in these paragraphs.

Every P0 and P1 item must have its **operational impact** stated in the prose, in ordinary language. Group related items into themes, but keep impacts distinct. Do not put `6.2.…` headings, finding numbers, or a parenthetical citation of each check in these paragraphs. The Priority Remediation List below is the inventory for Chapter 3.

Then a **Priority Remediation List** as a bulleted list of every P0 and P1:
- **P{n}** — {Chapter 6.2 heading}
Do not use `##` or `###` for that list; bullets only.

## Chapter 8. Conclusions

### 8.1 Close and cost of inaction

Close the assessment (snapshot, counts, P2/P3 are the bulk). Restate the cost of doing nothing on the P0/P1 themes. Overlap with Chapter 3 is expected. Do not walk every finding heading here.

### 8.2 Priority remediation

Write **phased prose**, not a finding catalog. Combine related P0 and P1 items into phases (typically live failures, then control-plane foundations, then upgrade/maintenance blockers, then isolation and networking). Every P0 and P1 item from the dump must appear **inside** those phases, with cost of doing nothing and Level of Impact (when not `none`) woven into the paragraphs.

Do **not** use `#### 6.2.…` headings. Do **not** use repeating labels such as `**Cost of doing nothing:**` or `**Level of Impact:**` under each finding. Bold **Phase N — short title (disruption class)** then write paragraphs.

Name findings in ordinary language (CrashLoopBackOff, etcd compaction, MachineConfigPool). Chapter 6.2 numbers belong in the Chapter 3 list, not as a second outline here.

Good shape: an opening sentence that the order works from live failures outward, then phases that group etcd disk / compaction / log errors as one control-plane storage effort, MCP before PDB, SCC then host-network as a separate window.

Bad shape: one `####` heading per finding with two labeled blocks under each.

### 8.3 Sequence and disruption

Do **not** repeat the Phase 1–4 walk. Two or three paragraphs only: what can run in parallel, what should not be a hard prerequisite, and what must not be deferred indefinitely (for example VM-owner windows). Point back to 8.2 rather than restating it.
