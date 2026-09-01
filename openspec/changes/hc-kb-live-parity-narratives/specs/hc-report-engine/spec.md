# Health Check Report Engine (`hc-kb-live-parity-narratives` delta)

## ADDED Requirements

### Requirement: Frozen native stubs receive full voice
KB rows listed in `tmp/hc_kb_live_parity_narratives/STUBS.txt` (non-comment lines) SHALL be native (`content_from` empty) and SHALL have `description` strip length at least 40 characters after this change. Evaluators and scoring fields SHALL NOT change in this change.

#### Scenario: Frozen native is no longer stub-length
- GIVEN production `load_kb()`
- AND a `check_id` listed in `STUBS.txt` (ignoring `#` lines)
- WHEN that entry is loaded
- THEN `content_from` is empty
- AND `len(description.strip())` is at least 40

#### Scenario: Empty freeze list needs no voice edits
- GIVEN `STUBS.txt` with no non-comment `check_id` lines
- WHEN this change is applied
- THEN no native scoring fields change
- AND `load_kb()` still succeeds

### Requirement: Voice pass does not overlay aliases
Alias rows (`content_from` set) SHALL NOT gain inherited narrative keys (`description`, `recommendation`, `verification`, impact, links) in this change. Overlay SHALL remain a `load_kb()` `ValueError`.

#### Scenario: Frozen natives do not overlay their aliases
- GIVEN a native `check_id` listed in `STUBS.txt` (non-comment lines)
- AND an alias row whose `content_from` equals that `check_id`
- WHEN the KB TOML files are read
- THEN the alias row does not set `description`, `recommendation`, or `verification`

#### Scenario: Empty freeze list leaves aliases unchanged
- GIVEN `STUBS.txt` with no non-comment `check_id` lines
- WHEN this change is applied
- THEN `load_kb()` succeeds
- AND no alias row gained inherited narrative keys from this change
