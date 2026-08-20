"""Parse documentation URLs into product, version, book, and fragment."""
from __future__ import annotations

from urllib.parse import ParseResult, urlparse

from hc_report.link_review.models import (
    OPENSHIFT_DOCS_HOST,
    OPENSHIFT_PRODUCT,
    ParsedDocUrl,
    REDHAT_DOCS_HOST,
)


def parse_documentation_url(url: str) -> ParsedDocUrl:
    original = url
    if not url or not url.strip():
        return _external_doc_url(original, "")
    parsed_url = urlparse(url.strip())
    hostname = (parsed_url.hostname or "").lower()
    if hostname == OPENSHIFT_DOCS_HOST:
        mapped = _parse_openshift_docs_path(original, parsed_url)
        if mapped is not None:
            return mapped
        return _external_doc_url(original, hostname)
    if hostname == REDHAT_DOCS_HOST:
        mapped = _parse_redhat_docs_path(original, parsed_url)
        if mapped is not None:
            return mapped
        return _external_doc_url(original, hostname)
    return _external_doc_url(original, hostname)


def _external_doc_url(original: str, hostname: str) -> ParsedDocUrl:
    return ParsedDocUrl(
        host=hostname,
        product="",
        version="",
        book_slug="",
        fragment="",
        original=original,
        is_external=True,
    )


def _path_parts(parsed_url: ParseResult) -> list[str]:
    parts: list[str] = []
    for part in parsed_url.path.split("/"):
        if part:
            parts.append(part)
    return parts


def _parse_openshift_docs_path(original: str, parsed_url: ParseResult) -> ParsedDocUrl | None:
    parts = _path_parts(parsed_url)
    if len(parts) < 3:
        return None
    if parts[0] != "container-platform":
        return None
    return ParsedDocUrl(
        host=REDHAT_DOCS_HOST,
        product=OPENSHIFT_PRODUCT,
        version=parts[1],
        book_slug=parts[2],
        fragment=parsed_url.fragment,
        original=original,
        is_external=False,
    )


def _parse_redhat_docs_path(original: str, parsed_url: ParseResult) -> ParsedDocUrl | None:
    parts = _path_parts(parsed_url)
    if len(parts) < 6:
        return None
    if parts[0] != "en" or parts[1] != "documentation":
        return None
    if parts[4] not in {"html-single", "html"}:
        return None
    return ParsedDocUrl(
        host=REDHAT_DOCS_HOST,
        product=parts[2],
        version=parts[3],
        book_slug=parts[5],
        fragment=parsed_url.fragment,
        original=original,
        is_external=False,
    )
