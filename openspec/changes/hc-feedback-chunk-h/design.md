# Design: hc-feedback-chunk-h

Renderer-only assembly plus one KB impact triple.

- `_STATUS_TAG_RE` recognizes `SUPPORT LIMITATION` before `LIMITATION`.
- Observation is count + one prose source (pattern XOR remainder).
- Remainder cap 400; Chapter 4 / pattern cap stays 220.
- Sentence terminator is `.!?` followed by whitespace or end of string.
- Grouped `Affected:` is compacted only in Observation; `Finding.description` keeps the full list.
- Chapter 4 `{CRITICAL_FINDINGS_SUMMARY}` becomes count lines + the P0/P1 table. `{CRITICAL_FINDINGS}` becomes a pointer.
- `7.4.tsr.4_8_1_3_4_node_disk` impact is `none` / virt StorageClass defaults.

Leaf `CheckResult.status` stays TSR WARNING when the HTML status is WARNING. LIMITATION tags are not a new finding priority.
