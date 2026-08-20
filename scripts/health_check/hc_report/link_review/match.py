"""Route KB checks to documentation products and suggest precise URLs."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from hc_report.link_review.docs_index import (
    PRODUCT_DIRECTORIES,
    extract_headings,
    load_book_text,
)
from hc_report.link_review.models import (
    LOGGING_PRODUCT,
    LOGGING_VERSION,
    OPENSHIFT_DOCS_HOST,
    OPENSHIFT_PRODUCT,
    HeadingRecord,
    LinkSuggestion,
    ParsedDocUrl,
)
from hc_report.link_review.parse_url import parse_documentation_url

PRODUCT_ROUTES: tuple[tuple[tuple[str, ...], str, tuple[str, ...]], ...] = (
    (
        ("logging", "loki", "lokistack", "clusterlogforwarder", "log_forward"),
        "red_hat_openshift_logging",
        ("configuring_logging", "installing_logging", "scheduling_resources"),
    ),
    (
        ("prometheus", "alertmanager", "thanos", "openshift-monitoring"),
        "monitoring_stack_for_red_hat_openshift",
        (
            "configuring_core_platform_monitoring",
            "managing_alerts",
            "troubleshooting_monitoring_issues",
        ),
    ),
    (
        ("odf", "ceph", "rook-ceph", "openshift_data_foundation"),
        "red_hat_openshift_data_foundation",
        (
            "managing_and_allocating_storage_resources",
            "troubleshooting_openshift_data_foundation",
        ),
    ),
    (
        ("kubevirt", "cnv", "virtualization", "vmi", "hyperconverged"),
        "openshift_container_platform",
        ("virtualization",),
    ),
    (
        ("etcd",),
        "openshift_container_platform",
        ("etcd", "scalability_and_performance"),
    ),
    (
        ("scc", "oauth", "rbac", "pod security"),
        "openshift_container_platform",
        ("authentication_and_authorization",),
    ),
    (
        ("ingress", "haproxy", "router"),
        "openshift_container_platform",
        ("ingress_and_load_balancing", "networking_overview"),
    ),
    (
        ("registry", "imagestream"),
        "openshift_container_platform",
        ("registry",),
    ),
    (
        ("machineconfig", "mcp", "machine-config"),
        "openshift_container_platform",
        ("machine_configuration", "machine_management"),
    ),
    (
        ("ovn", "sdn", "network policy", "ipsec"),
        "openshift_container_platform",
        ("networking_overview", "ovn_kubernetes_network_plugin"),
    ),
)

EXTERNAL_HOSTS = frozenset(
    {
        "kubernetes.io",
        "etcd.io",
        "access.redhat.com",
        "catalog.redhat.com",
        "raw.githubusercontent.com",
    }
)

_OCP_VERSION_IN_PATH = re.compile(r"/(4\.\d+)/")
_KEYWORD_TOKEN = re.compile(r"[A-Za-z0-9]{4,}")
_STUB_BOOKS = frozenset({"logging", "monitoring"})
_HIGHEST_INDEXED_VERSION = "4.22"


def route_documentation_product(
    check_id: str,
    title: str,
    description: str,
) -> tuple[str, tuple[str, ...]]:
    haystack = f"{check_id} {title} {_first_description_sentence(description)}".lower()
    for tokens, product, book_stems in PRODUCT_ROUTES:
        for token in tokens:
            if token.lower() in haystack:
                return product, book_stems
    return "", ()


def is_generic_landing(parsed: ParsedDocUrl, routed_product: str, heading_text: str) -> bool:
    original_host = (urlparse(parsed.original).hostname or "").lower()
    if original_host == OPENSHIFT_DOCS_HOST:
        return True
    if parsed.product == OPENSHIFT_PRODUCT and parsed.book_slug in _STUB_BOOKS:
        return True
    if parsed.book_slug == "operators":
        return True
    if not parsed.fragment:
        return True
    stripped = heading_text.strip()
    if stripped.startswith("About ") or stripped == "Overview":
        return True
    return False


def current_link_is_precise(parsed: ParsedDocUrl) -> bool:
    if not parsed.fragment:
        return False
    if parsed.book_slug in _STUB_BOOKS:
        return False
    if parsed.book_slug == "operators":
        return False
    return True


def score_heading(heading_text: str, keywords: tuple[str, ...]) -> int:
    heading_lower = heading_text.lower()
    score = 0
    storage_in_keywords = False
    for keyword in keywords:
        lowered = keyword.lower()
        if lowered == "storage":
            storage_in_keywords = True
        if lowered in heading_lower:
            score += 1
    if storage_in_keywords and "storage" in heading_lower:
        score += 2
    return score


def suggest_documentation_link(
    *,
    entry_title: str,
    check_id: str,
    description: str,
    version_key: str,
    current_url: str,
    docs_index: dict[tuple[str, str, str], Path],
    heading_cache: dict[Path, list[HeadingRecord]] | None = None,
) -> LinkSuggestion:
    if heading_cache is None:
        heading_cache = {}
    parsed = parse_documentation_url(current_url)
    hostname = (urlparse(current_url).hostname or "").lower()
    if parsed.is_external or _is_external_host(hostname):
        return _suggest_external(
            check_id=check_id,
            entry_title=entry_title,
            version_key=version_key,
            current_url=current_url,
        )
    if version_key == "4.20":
        return _suggest_blocked_or_proxy(
            entry_title=entry_title,
            check_id=check_id,
            description=description,
            current_url=current_url,
            docs_index=docs_index,
            heading_cache=heading_cache,
        )
    return _suggest_routed_book(
        entry_title=entry_title,
        check_id=check_id,
        description=description,
        version_key=version_key,
        current_url=current_url,
        docs_index=docs_index,
        parsed=parsed,
        heading_cache=heading_cache,
    )


def _is_external_host(hostname: str) -> bool:
    if hostname in EXTERNAL_HOSTS:
        return True
    for domain in EXTERNAL_HOSTS:
        suffix = "." + domain
        if hostname.endswith(suffix):
            return True
    return False


def _suggest_external(
    *,
    check_id: str,
    entry_title: str,
    version_key: str,
    current_url: str,
) -> LinkSuggestion:
    return LinkSuggestion(
        check_id=check_id,
        toml_file="",
        title=entry_title,
        version_key=version_key,
        current_url=current_url,
        suggested_url=current_url,
        verdict="EXTERNAL-UNCHECKED",
        confidence="HIGH",
        evidence="external host; not present in local documentation tree",
    )


def _suggest_blocked_or_proxy(
    *,
    entry_title: str,
    check_id: str,
    description: str,
    current_url: str,
    docs_index: dict[tuple[str, str, str], Path],
    heading_cache: dict[Path, list[HeadingRecord]],
) -> LinkSuggestion:
    suggestion_19 = suggest_documentation_link(
        entry_title=entry_title,
        check_id=check_id,
        description=description,
        version_key="4.19",
        current_url=_rewrite_ocp_version(current_url, "4.19"),
        docs_index=docs_index,
        heading_cache=heading_cache,
    )
    suggestion_21 = suggest_documentation_link(
        entry_title=entry_title,
        check_id=check_id,
        description=description,
        version_key="4.21",
        current_url=_rewrite_ocp_version(current_url, "4.21"),
        docs_index=docs_index,
        heading_cache=heading_cache,
    )
    masked_19 = _mask_minor_version(suggestion_19.suggested_url)
    masked_21 = _mask_minor_version(suggestion_21.suggested_url)
    if suggestion_19.suggested_url and masked_19 == masked_21:
        proxied_url = _rewrite_ocp_version(suggestion_19.suggested_url, "4.20")
        return LinkSuggestion(
            check_id=check_id,
            toml_file="",
            title=entry_title,
            version_key="4.20",
            current_url=current_url,
            suggested_url=proxied_url,
            verdict="PROXY-4.19/4.21",
            confidence=suggestion_19.confidence,
            evidence="4.19 and 4.21 suggested path+fragment match (version stripped)",
        )
    return LinkSuggestion(
        check_id=check_id,
        toml_file="",
        title=entry_title,
        version_key="4.20",
        current_url=current_url,
        suggested_url="",
        verdict="BLOCKED-DOCS",
        confidence="LOW",
        evidence="4.19 and 4.21 suggestions differ or are empty; no local 4.20 tree",
    )


def _suggest_routed_book(
    *,
    entry_title: str,
    check_id: str,
    description: str,
    version_key: str,
    current_url: str,
    docs_index: dict[tuple[str, str, str], Path],
    parsed: ParsedDocUrl,
    heading_cache: dict[Path, list[HeadingRecord]],
) -> LinkSuggestion:
    product, book_stems = _resolve_route(check_id, entry_title, description, parsed)
    index_version, url_version = _versions_for_suggestion(product, version_key, current_url)
    keywords = _keyword_tokens(check_id, entry_title, description)
    heading = _best_heading_in_stems(
        product, index_version, book_stems, docs_index, keywords, heading_cache
    )
    book_slug, fragment, confidence, evidence = _fragment_from_heading(
        parsed, heading, book_stems
    )
    if book_slug:
        suggested_url = _build_docs_url(product, url_version, book_slug, fragment)
    else:
        suggested_url = current_url
    heading_text = heading.heading_text if heading is not None else ""
    generic = is_generic_landing(parsed, product, heading_text)
    verdict = _verdict_for_change(parsed, product, book_slug, fragment, generic)
    if verdict == "BOOK-HINT":
        suggested_url = current_url
    return LinkSuggestion(
        check_id=check_id,
        toml_file="",
        title=entry_title,
        version_key=version_key,
        current_url=current_url,
        suggested_url=suggested_url,
        verdict=verdict,
        confidence=confidence,
        evidence=evidence,
    )


def _resolve_route(
    check_id: str,
    title: str,
    description: str,
    parsed: ParsedDocUrl,
) -> tuple[str, tuple[str, ...]]:
    product, book_stems = route_documentation_product(check_id, title, description)
    if product:
        return product, book_stems
    fallback_stems = (parsed.book_slug,) if parsed.book_slug else ()
    if parsed.product in PRODUCT_DIRECTORIES:
        return parsed.product, fallback_stems
    return OPENSHIFT_PRODUCT, fallback_stems


def _versions_for_suggestion(
    product: str,
    version_key: str,
    current_url: str,
) -> tuple[str, str]:
    if product == LOGGING_PRODUCT:
        return LOGGING_VERSION, LOGGING_VERSION
    if version_key == "default":
        if "/latest/" in current_url:
            return _HIGHEST_INDEXED_VERSION, "latest"
        return _HIGHEST_INDEXED_VERSION, _HIGHEST_INDEXED_VERSION
    return version_key, version_key


def _keyword_tokens(check_id: str, title: str, description: str) -> tuple[str, ...]:
    blob = f"{check_id} {title} {_first_description_sentence(description)}"
    tokens: list[str] = []
    seen: set[str] = set()
    for token in _KEYWORD_TOKEN.findall(blob.lower()):
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tuple(tokens)


def _first_description_sentence(description: str) -> str:
    return description.split(".", 1)[0]


def _best_heading_in_stems(
    product: str,
    index_version: str,
    book_stems: tuple[str, ...],
    docs_index: dict[tuple[str, str, str], Path],
    keywords: tuple[str, ...],
    heading_cache: dict[Path, list[HeadingRecord]],
) -> HeadingRecord | None:
    best = _max_heading_for_stems(
        product, index_version, book_stems, docs_index, keywords, heading_cache
    )
    if best is not None:
        return best
    return _max_heading_for_product(
        product, index_version, docs_index, keywords, heading_cache
    )


def _max_heading_for_stems(
    product: str,
    index_version: str,
    book_stems: tuple[str, ...],
    docs_index: dict[tuple[str, str, str], Path],
    keywords: tuple[str, ...],
    heading_cache: dict[Path, list[HeadingRecord]],
) -> HeadingRecord | None:
    best: HeadingRecord | None = None
    best_score = -1
    for stem in book_stems:
        path = docs_index.get((product, index_version, stem))
        if path is None:
            continue
        headings = _headings_from_path(path, product, index_version, stem, heading_cache)
        best, best_score = _maybe_better_heading(headings, keywords, best, best_score)
    return best


def _max_heading_for_product(
    product: str,
    index_version: str,
    docs_index: dict[tuple[str, str, str], Path],
    keywords: tuple[str, ...],
    heading_cache: dict[Path, list[HeadingRecord]],
) -> HeadingRecord | None:
    best: HeadingRecord | None = None
    best_score = -1
    for key, path in docs_index.items():
        indexed_product, indexed_version, book_slug = key
        if indexed_product != product or indexed_version != index_version:
            continue
        headings = _headings_from_path(path, product, index_version, book_slug, heading_cache)
        best, best_score = _maybe_better_heading(headings, keywords, best, best_score)
    return best


def _maybe_better_heading(
    headings: list[HeadingRecord],
    keywords: tuple[str, ...],
    best: HeadingRecord | None,
    best_score: int,
) -> tuple[HeadingRecord | None, int]:
    chosen = best
    score_floor = best_score
    for heading in headings:
        score = score_heading(heading.heading_text, keywords)
        if score > score_floor:
            score_floor = score
            chosen = heading
    return chosen, score_floor


def _headings_from_path(
    path: Path,
    product: str,
    version: str,
    book_slug: str,
    heading_cache: dict[Path, list[HeadingRecord]],
) -> list[HeadingRecord]:
    cached = heading_cache.get(path)
    if cached is not None:
        return cached
    try:
        text = load_book_text(path)
    except OSError:
        return []
    headings = extract_headings(text, path, product, version, book_slug)
    heading_cache[path] = headings
    return headings


def _fragment_from_heading(
    parsed: ParsedDocUrl,
    heading: HeadingRecord | None,
    book_stems: tuple[str, ...],
) -> tuple[str, str, str, str]:
    if heading is None:
        book_slug = book_stems[0] if book_stems else parsed.book_slug
        fragment = parsed.fragment if book_slug == parsed.book_slug else ""
        return book_slug, fragment, "LOW", "no matching heading in local documentation index"
    book_slug = heading.book_slug
    if book_slug == parsed.book_slug:
        evidence = heading.heading_text
        if parsed.fragment:
            return book_slug, parsed.fragment, "HIGH", evidence
        return book_slug, "", "LOW", evidence
    evidence = f"local heading hint (not used as URL fragment): {heading.heading_text}"
    return book_slug, "", "MEDIUM", evidence


def _verdict_for_change(
    parsed: ParsedDocUrl,
    product: str,
    book_slug: str,
    fragment: str,
    generic: bool,
) -> str:
    same_book = parsed.product == product and parsed.book_slug == book_slug
    if generic:
        if same_book and parsed.fragment == fragment:
            return "KEEP"
        if not same_book or fragment:
            return "REPLACE"
        return "KEEP"
    if current_link_is_precise(parsed) and not same_book:
        return "BOOK-HINT"
    if same_book:
        return "KEEP"
    return "BOOK-HINT"


def _build_docs_url(product: str, version: str, book_slug: str, fragment: str) -> str:
    base = (
        f"https://docs.redhat.com/en/documentation/{product}/{version}"
        f"/html-single/{book_slug}/index"
    )
    if fragment:
        return f"{base}#{fragment}"
    return base


def _mask_minor_version(url: str) -> str:
    return _OCP_VERSION_IN_PATH.sub("/X/", url)


def _rewrite_ocp_version(url: str, version: str) -> str:
    return _OCP_VERSION_IN_PATH.sub(f"/{version}/", url, count=1)
