# Health Check Report Engine (`content_from` delta)

## ADDED Requirements

### Requirement: KB content_from alias
An alias KB row MAY set `content_from` to an exact canonical `check_id`. `load_kb()` SHALL copy inherited content from that target in a single hop and SHALL keep the alias `check_id` and finding flags on the alias. Overlay, chains, self-references, missing targets, pattern-row pointers, and glob targets SHALL raise `ValueError`.

#### Scenario: Alias inherits content and keeps local title and flags
- GIVEN alias `content_from = "canonical.id"` and omitted inherited keys
- WHEN `load_kb()` runs
- THEN `get_entry(alias)` recommendation, description, impact, and links equal the canonical row
- AND title stays the alias title
- AND `include_in_findings` stays the alias value

#### Scenario: Missing target fails closed
- GIVEN `content_from` target missing from `entries`
- WHEN `load_kb()` runs
- THEN `ValueError`

#### Scenario: Self-reference fails closed
- GIVEN alias `content_from` equals its own `check_id`
- WHEN `load_kb()` runs
- THEN `ValueError`

#### Scenario: Chain fails closed
- GIVEN A→B and B also has `content_from`
- WHEN `load_kb()` runs
- THEN `ValueError` (chain forbidden; this covers cycles)

#### Scenario: Overlay inherited fields fail closed
- GIVEN alias sets a non-empty `recommendation` (or any other inherited field)
- WHEN `load_kb()` runs
- THEN `ValueError`

#### Scenario: Pattern entry pointer fails closed
- GIVEN `pattern = true` and `content_from` set
- WHEN `load_kb()` runs
- THEN `ValueError`

#### Scenario: Glob target fails closed
- GIVEN target is only a glob in `pattern_entries`
- WHEN `load_kb()` runs
- THEN `ValueError`
