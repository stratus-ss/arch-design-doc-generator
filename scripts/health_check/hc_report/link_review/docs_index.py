"""Index local OpenShift documentation text extracts and their headings."""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from hc_report.link_review.models import LOGGING_PRODUCT, LOGGING_VERSION, HeadingRecord

PRODUCT_DIRECTORIES: dict[str, str] = {
    "openshift_container_platform": "Openshift_Container_Platform-{version}-docs",
    "monitoring_stack_for_red_hat_openshift": (
        "Monitoring_Stack_For_Red_Hat_Openshift-{version}-docs"
    ),
    "red_hat_openshift_data_foundation": "Red_Hat_Openshift_Data_Foundation-{version}-docs",
    "red_hat_openshift_logging": "Red_Hat_Openshift_Logging-6.5-docs",
}

_INDEXED_VERSIONS = ("4.18", "4.19", "4.21", "4.22")
_CHAPTER_HEADING = re.compile(r"^\s*CHAPTER\s+(\d+)\.\s+(\S.*?)\s*$", re.IGNORECASE)
_SECTION_HEADING = re.compile(r"^\s*(\d+(?:\.\d+)+)\.\s+(\S.*)$")
_DOTTED_LEADERS = re.compile(r"(?:\.\s*){2,}")
_TRAILING_PAGE_NUMBER = re.compile(r"\s+\d+\s*$")
_MULTI_SPACE = re.compile(r"\s+")
_SKIPPED_HEADING_MARKERS = ("table of contents", "legal notice", "abstract")


def build_docs_index(docs_root: Path) -> dict[tuple[str, str, str], Path]:
    index: dict[tuple[str, str, str], Path] = {}
    for product, version, product_directory in _iter_product_directories(docs_root):
        for book_path in _iter_book_files(product_directory):
            book_slug = _book_slug_from_filename(book_path.name, product_directory.name)
            if not book_slug:
                continue
            index[(product, version, book_slug)] = book_path
    return index


def load_book_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise OSError(f"Unable to read {path}: {error}") from error


def extract_headings(
    text: str,
    source_path: Path,
    product: str,
    version: str,
    book_slug: str,
) -> list[HeadingRecord]:
    headings: list[HeadingRecord] = []
    for raw_line in text.splitlines():
        heading_text = _heading_from_line(raw_line)
        if heading_text is None:
            continue
        if _is_skipped_heading(heading_text):
            continue
        headings.append(
            HeadingRecord(
                product=product,
                version=version,
                book_slug=book_slug,
                heading_text=heading_text,
                source_path=source_path,
            )
        )
    return headings


def _iter_product_directories(docs_root: Path) -> Iterator[tuple[str, str, Path]]:
    for product, pattern in PRODUCT_DIRECTORIES.items():
        if product == LOGGING_PRODUCT:
            product_directory = docs_root / pattern
            if product_directory.is_dir():
                yield product, LOGGING_VERSION, product_directory
            continue
        for version in _INDEXED_VERSIONS:
            product_directory = docs_root / pattern.format(version=version)
            if product_directory.is_dir():
                yield product, version, product_directory


def _iter_book_files(product_directory: Path) -> list[Path]:
    text_directory = product_directory / "txt"
    if text_directory.is_dir():
        return sorted(text_directory.glob("*-en-US.txt"))
    return sorted(product_directory.glob("*-en-US.txt"))


def _book_slug_from_filename(filename: str, directory_name: str) -> str:
    prefix = directory_name.removesuffix("-docs") + "-"
    suffix = "-en-US.txt"
    if not filename.startswith(prefix) or not filename.endswith(suffix):
        return ""
    return filename[len(prefix) : -len(suffix)]


def _heading_from_line(raw_line: str) -> str | None:
    cleaned = _DOTTED_LEADERS.sub(" ", raw_line)
    chapter_match = _CHAPTER_HEADING.match(cleaned)
    if chapter_match:
        number = chapter_match.group(1)
        title = _clean_heading_title(chapter_match.group(2))
        if not title:
            return None
        return f"CHAPTER {number}. {title}"
    section_match = _SECTION_HEADING.match(cleaned)
    if section_match:
        number = section_match.group(1)
        title = _clean_heading_title(section_match.group(2))
        if not title:
            return None
        return f"{number}. {title}"
    return None


def _clean_heading_title(title: str) -> str:
    stripped = _TRAILING_PAGE_NUMBER.sub("", title).strip()
    return _MULTI_SPACE.sub(" ", stripped).strip()


def _is_skipped_heading(heading_text: str) -> bool:
    normalized = heading_text.strip().lower()
    for marker in _SKIPPED_HEADING_MARKERS:
        if marker in normalized:
            return True
    return False
