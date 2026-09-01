# Design: native KB voice pass (stubs)

Freeze native `check_id`s from `load_kb()` where `content_from` is empty and `len(description.strip()) < 40`. Cap at 25 (longest-lived chapter prefix first via sort). Fill TOML voice only on that list. Do not invent FAIL conditions. Match existing evaluator bars. Do not set inherited fields on alias rows.

If the freeze file has no non-comment ids, skip KB edits. Allowlisted pytest still reads the freeze file and treats an empty list as success.

Voice follows existing KB contracts: rec-first imperative English (end state, then change or accepted risk); numbered `oc` in `verification` with sentence titles a technical reader can follow without knowing the scorer; `description` mode-neutral (what the check evaluates, not one cluster's TSR remainder).
