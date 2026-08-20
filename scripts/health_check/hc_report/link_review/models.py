"""Dataclasses and shared constants for documentation link review."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

OPENSHIFT_PRODUCT = "openshift_container_platform"
REDHAT_DOCS_HOST = "docs.redhat.com"
OPENSHIFT_DOCS_HOST = "docs.openshift.com"
LOGGING_PRODUCT = "red_hat_openshift_logging"
LOGGING_VERSION = "6.5"


@dataclass(frozen=True)
class ParsedDocUrl:
    host: str
    product: str
    version: str
    book_slug: str
    fragment: str
    original: str
    is_external: bool


@dataclass(frozen=True)
class HeadingRecord:
    product: str
    version: str
    book_slug: str
    heading_text: str
    source_path: Path


@dataclass(frozen=True)
class LinkSuggestion:
    check_id: str
    toml_file: str
    title: str
    version_key: str
    current_url: str
    suggested_url: str
    verdict: str
    confidence: str
    evidence: str
