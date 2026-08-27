"""Load and query the health-check TOML knowledge base."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # Python 3.10 fallback

NEEDS_REVIEW_MARKER = "[NEEDS REVIEW]"
INHERITED_CONTENT_FIELDS = (
    "recommendation",
    "verification",
    "description",
    "impact",
    "impact_scope",
    "impact_detail",
    "links",
    "recommendation_supported_versions",
    "priority_hint",
    "summary_patterns",
)
VERIFICATION_JOIN_LABEL = "**Verification:**"
VERIFICATION_SPLIT_LABELS = frozenset({"Verification:", "**Verification:**"})
REFERENCE_JOIN_LABEL = "**Reference:**"
_DEFAULT_LINK_KEY = "default"
_DEFAULT_KB_DIR = Path(__file__).resolve().parent / "kb"
_VERSION_PATTERN = re.compile(r"^(\d+\.\d+)")
_REDHAT_DOCS_PREFIX = "https://docs.redhat.com/en/documentation/"


def is_versioned_doc_link_key(key: str) -> bool:
    return bool(_VERSION_PATTERN.fullmatch(str(key).strip()))


def extra_reference_links(links: dict[str, str], primary_link: str) -> list[str]:
    extras: list[str] = []
    for key, url in links.items():
        if key == _DEFAULT_LINK_KEY or is_versioned_doc_link_key(key):
            continue
        if url and url != primary_link and url not in extras:
            extras.append(url)
    return extras


def split_recommendation_blob(blob: str) -> tuple[str, str]:
    normalized = blob.replace("\r\n", "\n")
    lines = normalized.split("\n")
    hit_indexes: list[int] = []
    for index, line in enumerate(lines):
        if line.strip() in VERIFICATION_SPLIT_LABELS:
            hit_indexes.append(index)
    if len(hit_indexes) > 1:
        raise ValueError("multiple Verification labels")
    if not hit_indexes:
        return normalized.strip(), ""
    split_at = hit_indexes[0]
    recommendation = "\n".join(lines[:split_at]).strip()
    verification = "\n".join(lines[split_at + 1 :]).strip()
    return recommendation, verification


def join_recommendation_parts(recommendation: str, verification: str) -> str:
    recommendation = recommendation.strip()
    verification = verification.strip()
    if not verification:
        return recommendation
    return f"{recommendation}\n\n{VERIFICATION_JOIN_LABEL}\n{verification}"


@dataclass(frozen=True)
class SummaryPattern:
    contains: str
    text: str


@dataclass(frozen=True)
class KBEntry:
    check_id: str
    title: str = ""
    description: str = ""
    recommendation: str = ""
    verification: str = ""
    recommendation_supported_versions: tuple[str, ...] = field(default_factory=tuple)
    priority_hint: str = ""
    impact: str = ""
    impact_scope: str = ""
    impact_detail: str = ""
    summary_patterns: tuple[SummaryPattern, ...] = field(default_factory=tuple)
    finding_group: str = ""
    finding_group_title: str = ""
    include_in_findings: bool = True
    finding_on_info: bool = False
    links: dict[str, str] = field(default_factory=dict)
    is_pattern: bool = False
    content_from: str = ""


@dataclass
class KnowledgeBase:
    entries: dict[str, KBEntry]
    active_versions: list[str]
    pattern_entries: list[tuple[re.Pattern, KBEntry]] = field(default_factory=list)
    _loaded: bool = False

    def get_entry(self, check_id: str) -> KBEntry | None:
        """Look up an exact check_id match first, then fall back to the first
        registered glob pattern (e.g. `7.2.node.*.sysreserved`) whose regex
        matches. Dynamic fan-out check families (per-node, per-subscription)
        use patterns so one KB entry can cover an unbounded number of
        generated check_ids.
        """
        entry = self.entries.get(check_id)
        if entry is not None:
            return entry
        for pattern, pattern_entry in self.pattern_entries:
            if pattern.match(check_id):
                return pattern_entry
        return None

    def get_recommendation(self, check_id: str, ocp_version: str) -> str:
        entry = self.get_entry(check_id)
        if entry is None or not entry.recommendation.strip():
            return NEEDS_REVIEW_MARKER
        recommendation = join_recommendation_parts(
            entry.recommendation, entry.verification
        )
        resolved_version = resolve_version(ocp_version, self.active_versions)
        if (
            entry.recommendation_supported_versions
            and resolved_version not in entry.recommendation_supported_versions
        ):
            requested_version = _extract_minor_version(ocp_version) or str(ocp_version).strip() or _DEFAULT_LINK_KEY
            supported_versions = ", ".join(entry.recommendation_supported_versions)
            return (
                f"{NEEDS_REVIEW_MARKER}\n\n"
                f"The recommendation for `{check_id}` is validated only for OCP {supported_versions}. "
                f"Requested version `{requested_version}` requires manual review before using this guidance.\n\n"
                f"Candidate guidance:\n{recommendation}"
            )
        link = self.get_doc_link(check_id, ocp_version)
        missing_links = [
            url
            for url in (link, *extra_reference_links(entry.links, link))
            if url and url not in recommendation
        ]
        if missing_links:
            return (
                f"{recommendation.rstrip()}\n\n{REFERENCE_JOIN_LABEL} "
                + "\n".join(missing_links)
            )
        return recommendation

    def get_description(self, check_id: str) -> str:
        entry = self.get_entry(check_id)
        return entry.description.strip() if entry else ""

    def get_title(self, check_id: str) -> str:
        entry = self.get_entry(check_id)
        return entry.title.strip() if entry else ""

    def get_doc_link(self, check_id: str, ocp_version: str) -> str:
        entry = self.get_entry(check_id)
        if entry is None or not entry.links:
            return ""
        resolved_version = resolve_version(ocp_version, self.active_versions)
        version_link = entry.links.get(resolved_version)
        if version_link:
            return version_link
        default_link = entry.links.get(_DEFAULT_LINK_KEY, "")
        return _resolve_default_doc_link(default_link, resolved_version)

    def get_note(self, check_id: str, ocp_version: str) -> tuple[str, str] | None:
        entry = self.get_entry(check_id)
        if entry is None or not entry.description.strip():
            return None
        return entry.description.strip(), self.get_doc_link(check_id, ocp_version)

    def get_impact(self, check_id: str) -> tuple[str, str, str] | None:
        entry = self.get_entry(check_id)
        if entry is None or not entry.impact.strip():
            return None
        return (
            entry.impact.strip(),
            entry.impact_scope.strip(),
            entry.impact_detail.strip(),
        )


def format_impact_line(impact: str, impact_scope: str, impact_detail: str) -> str:
    """Render a **Level of Impact:** markdown line from raw KB fields.

    Mirrors the canonical rendering in renderer._format_impact_block so
    both generation and post-hoc update produce identical output.
    """
    if not impact:
        return f"**Level of Impact:** {NEEDS_REVIEW_MARKER}"
    if impact == "none":
        label = "None"
    else:
        label = impact.replace("-", " ").title()
    scope = f" ({impact_scope})" if impact_scope else ""
    detail = f" — {impact_detail}" if impact_detail else ""
    return f"**Level of Impact:** {label}{scope}{detail}"


_KB_CACHE: KnowledgeBase | None = None
_KB_CACHE_DIR: Path | None = None


def _normalize_links(raw_links: object) -> dict[str, str]:
    if not isinstance(raw_links, dict):
        return {}
    links: dict[str, str] = {}
    for key, value in raw_links.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if key_text and value_text:
            links[key_text] = value_text
    return links


def _normalize_versions(raw_versions: object) -> tuple[str, ...]:
    if not isinstance(raw_versions, list):
        return ()
    versions: list[str] = []
    for value in raw_versions:
        version = str(value).strip()
        if version:
            versions.append(version)
    return tuple(versions)


def _normalize_summary_patterns(raw_patterns: object, source_path: Path) -> tuple[SummaryPattern, ...]:
    if raw_patterns is None:
        return ()
    if not isinstance(raw_patterns, list):
        raise ValueError(f"Invalid summary_patterns in {source_path}: expected a list")
    if not raw_patterns:
        return ()
    patterns: list[SummaryPattern] = []
    for item in raw_patterns:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid summary_patterns in {source_path}: expected tables")
        contains = str(item.get("contains", "")).strip()
        text = str(item.get("text", "")).strip()
        if not contains or not text:
            raise ValueError(
                f"Invalid summary_patterns in {source_path}: contains and text are required"
            )
        patterns.append(SummaryPattern(contains=contains, text=text))
    return tuple(patterns)


def _normalize_finding_group(raw_value: object) -> str:
    if raw_value is None:
        return ""
    return str(raw_value).strip()


def _normalize_include_in_findings(raw_value: object, source_path: Path) -> bool:
    if raw_value is None:
        return True
    if isinstance(raw_value, bool):
        return raw_value
    raise ValueError(f"Invalid include_in_findings in {source_path}: expected a bool")


def _normalize_finding_on_info(raw_value: object, source_path: Path) -> bool:
    if raw_value is None:
        return False
    if isinstance(raw_value, bool):
        return raw_value
    raise ValueError(f"Invalid finding_on_info in {source_path}: expected a bool")


def _load_toml_file(path: Path) -> dict:
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"Invalid TOML in {path}: {error}") from error
    except OSError as error:
        raise OSError(f"Unable to read {path}: {error}") from error


def _make_entry(raw_entry: object, source_path: Path) -> KBEntry:
    if not isinstance(raw_entry, dict):
        raise ValueError(f"Invalid KB entry in {source_path}: expected a table")
    check_id = str(raw_entry.get("check_id", "")).strip()
    if not check_id:
        raise ValueError(f"Invalid KB entry in {source_path}: missing check_id")
    return KBEntry(
        check_id=check_id,
        title=str(raw_entry.get("title", "")).strip(),
        description=str(raw_entry.get("description", "")).strip(),
        recommendation=str(raw_entry.get("recommendation", "")).strip(),
        verification=str(raw_entry.get("verification", "")).strip(),
        recommendation_supported_versions=_normalize_versions(
            raw_entry.get("recommendation_supported_versions", [])
        ),
        priority_hint=str(raw_entry.get("priority_hint", "")).strip(),
        impact=str(raw_entry.get("impact", "")).strip(),
        impact_scope=str(raw_entry.get("impact_scope", "")).strip(),
        impact_detail=str(raw_entry.get("impact_detail", "")).strip(),
        summary_patterns=_normalize_summary_patterns(
            raw_entry.get("summary_patterns"), source_path
        ),
        finding_group=_normalize_finding_group(raw_entry.get("finding_group")),
        finding_group_title=_normalize_finding_group(raw_entry.get("finding_group_title")),
        include_in_findings=_normalize_include_in_findings(
            raw_entry.get("include_in_findings"), source_path
        ),
        finding_on_info=_normalize_finding_on_info(
            raw_entry.get("finding_on_info"), source_path
        ),
        links=_normalize_links(raw_entry.get("links", {})),
        is_pattern=bool(raw_entry.get("pattern", False)),
        content_from=str(raw_entry.get("content_from", "")).strip(),
    )


def _compile_check_id_pattern(glob_pattern: str) -> re.Pattern:
    """Compile a check_id glob (`*` wildcard) into an anchored regex."""
    escaped = re.escape(glob_pattern).replace(r"\*", ".*")
    return re.compile(f"^{escaped}$")


def load_active_versions(kb_dir: Path | None = None) -> list[str]:
    base_dir = (kb_dir or _DEFAULT_KB_DIR).resolve()
    manifest = _load_toml_file(base_dir / "versions.toml")
    raw_versions = manifest.get("active_versions", {}).get("versions", [])
    return [str(version).strip() for version in raw_versions if str(version).strip()]


def resolve_version(ocp_version: str, active_versions: list[str]) -> str:
    match = _VERSION_PATTERN.match(str(ocp_version).strip())
    if not match:
        return _DEFAULT_LINK_KEY
    minor_version = match.group(1)
    if minor_version in active_versions:
        return minor_version
    return _DEFAULT_LINK_KEY


def _extract_minor_version(ocp_version: str) -> str:
    match = _VERSION_PATTERN.match(str(ocp_version).strip())
    return match.group(1) if match else ""


def _resolve_default_doc_link(default_link: str, resolved_version: str) -> str:
    if not default_link or resolved_version == _DEFAULT_LINK_KEY:
        return default_link
    if not default_link.startswith(_REDHAT_DOCS_PREFIX):
        return default_link
    return default_link.replace("/latest/", f"/{resolved_version}/", 1)


def _field_is_populated(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, tuple):
        return bool(value)
    return bool(value)


def _alias_sets_inherited_content(entry: KBEntry) -> bool:
    for field_name in INHERITED_CONTENT_FIELDS:
        if _field_is_populated(getattr(entry, field_name)):
            return True
    return False


def _require_exact_canonical_target(
    entry: KBEntry, entries: dict[str, KBEntry]
) -> KBEntry:
    if entry.content_from == entry.check_id:
        raise ValueError(f"KB content_from self-reference: {entry.check_id}")
    target_entry = entries.get(entry.content_from)
    if target_entry is None:
        raise ValueError(
            f"KB content_from target not found: {entry.check_id} -> {entry.content_from}"
        )
    if target_entry.content_from:
        raise ValueError(
            f"KB content_from chain forbidden: {entry.check_id} -> {entry.content_from}"
        )
    return target_entry


def _canonical_target_for_alias(
    entry: KBEntry, entries: dict[str, KBEntry]
) -> KBEntry:
    if entry.is_pattern:
        raise ValueError(
            f"KB content_from not allowed on pattern entries: {entry.check_id}"
        )
    if _alias_sets_inherited_content(entry):
        raise ValueError(
            f"KB content_from alias sets inherited fields: {entry.check_id}"
        )
    return _require_exact_canonical_target(entry, entries)


def _copy_inherited_content(alias_entry: KBEntry, target_entry: KBEntry) -> KBEntry:
    return replace(
        alias_entry,
        recommendation=target_entry.recommendation,
        verification=target_entry.verification,
        description=target_entry.description,
        impact=target_entry.impact,
        impact_scope=target_entry.impact_scope,
        impact_detail=target_entry.impact_detail,
        links=target_entry.links,
        recommendation_supported_versions=target_entry.recommendation_supported_versions,
        priority_hint=target_entry.priority_hint,
        summary_patterns=target_entry.summary_patterns,
    )


def _resolve_content_from(entries: dict[str, KBEntry]) -> dict[str, KBEntry]:
    resolved: dict[str, KBEntry] = {}
    for check_id, entry in entries.items():
        if not entry.content_from:
            resolved[check_id] = entry
            continue
        target_entry = _canonical_target_for_alias(entry, entries)
        resolved[check_id] = _copy_inherited_content(entry, target_entry)
    return resolved


def load_kb(kb_dir: Path | None = None) -> KnowledgeBase:
    global _KB_CACHE, _KB_CACHE_DIR

    base_dir = (kb_dir or _DEFAULT_KB_DIR).resolve()
    if _KB_CACHE is not None and _KB_CACHE_DIR == base_dir:
        return _KB_CACHE

    entries: dict[str, KBEntry] = {}
    pattern_entries: list[tuple[re.Pattern, KBEntry]] = []
    for path in sorted(base_dir.glob("7_*.toml")):
        data = _load_toml_file(path)
        for raw_entry in data.get("checks", []):
            entry = _make_entry(raw_entry, path)
            if entry.is_pattern:
                if entry.content_from:
                    raise ValueError(
                        f"KB content_from not allowed on pattern entries: {entry.check_id}"
                    )
                pattern_entries.append((_compile_check_id_pattern(entry.check_id), entry))
                continue
            if entry.check_id in entries:
                raise ValueError(f"Duplicate KB entry for {entry.check_id} in {path}")
            entries[entry.check_id] = entry

    entries = _resolve_content_from(entries)
    knowledge_base = KnowledgeBase(
        entries=entries,
        active_versions=load_active_versions(base_dir),
        pattern_entries=pattern_entries,
        _loaded=True,
    )
    _KB_CACHE = knowledge_base
    _KB_CACHE_DIR = base_dir
    return knowledge_base
