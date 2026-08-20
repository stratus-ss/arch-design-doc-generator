"""HTTP GET checks for suggested documentation page URLs (no fragment).

Prefers curl_cffi Chrome TLS impersonation (the container backend used by
the sibling repo's validate_links.py). Falls back to urllib if curl_cffi
is not installed. Fragments are stripped: a 200 means the page exists.
"""
from __future__ import annotations

import http.cookiejar
import random
import sys
import time
from dataclasses import replace
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from hc_report.link_review.models import LinkSuggestion

try:
    from curl_cffi.requests.exceptions import RequestException as _CurlRequestException
    from curl_cffi.requests.exceptions import Timeout as _CurlTimeout

    _CURL_TIMEOUT_EXCEPTIONS: tuple[type[BaseException], ...] = (_CurlTimeout,)
    _CURL_REQUEST_EXCEPTIONS: tuple[type[BaseException], ...] = (
        _CurlRequestException,
    )
except ImportError:
    _CURL_TIMEOUT_EXCEPTIONS = ()
    _CURL_REQUEST_EXCEPTIONS = ()

_DEFAULT_TIMEOUT_SECONDS = 15
_DEFAULT_RETRY_COUNT = 2
_RESPONSE_READ_LIMIT = 1024
_DELAY_MIN_SECONDS = 2.0
_DELAY_MAX_SECONDS = 5.0
_BATCH_SIZE = 10
_BATCH_PAUSE_SECONDS = 30.0
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)
_DEFAULT_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

PageStatusChecker = Callable[[str], int | str]


def url_without_fragment(url: str) -> str:
    return url.split("#", 1)[0]


def build_page_status_checker() -> PageStatusChecker:
    curl_session = _maybe_curl_session()
    urllib_opener = _build_urllib_opener()
    request_count = {"value": 0}
    if curl_session is not None:
        print("HTTP backend: curl_cffi (browser TLS fingerprint)", file=sys.stderr)
    else:
        print("HTTP backend: urllib (curl_cffi not installed)", file=sys.stderr)

    def check_status(url: str) -> int | str:
        _pace_request(request_count["value"])
        request_count["value"] += 1
        return _check_url_with_retry(url, curl_session, urllib_opener)

    return check_status


def apply_page_checks(
    suggestions: list[LinkSuggestion],
    check_status: PageStatusChecker,
) -> list[LinkSuggestion]:
    statuses: dict[str, int | str] = {}
    for suggestion in suggestions:
        page_url = _page_url_to_check(suggestion)
        if page_url is None or page_url in statuses:
            continue
        statuses[page_url] = check_status(page_url)
    updated: list[LinkSuggestion] = []
    for suggestion in suggestions:
        updated.append(_apply_status(suggestion, statuses))
    return updated


def _maybe_curl_session() -> object | None:
    try:
        from curl_cffi.requests import Session  # type: ignore[import-not-found]
    except ImportError:
        return None
    return Session(impersonate="chrome")


def _build_urllib_opener() -> object:
    jar = http.cookiejar.CookieJar()
    return build_opener(HTTPCookieProcessor(jar))


def _pace_request(completed: int) -> None:
    if completed == 0:
        return
    time.sleep(random.uniform(_DELAY_MIN_SECONDS, _DELAY_MAX_SECONDS))
    if _BATCH_SIZE > 0 and completed % _BATCH_SIZE == 0:
        print(
            f"  … batch pause ({_BATCH_PAUSE_SECONDS:.0f}s after {completed} requests)",
            file=sys.stderr,
        )
        time.sleep(_BATCH_PAUSE_SECONDS)


def _check_url_with_retry(
    url: str,
    curl_session: object | None,
    urllib_opener: object,
) -> int | str:
    attempts = _DEFAULT_RETRY_COUNT + 1
    status: int | str = "error"
    for attempt in range(attempts):
        try:
            return _request_status(url, curl_session, urllib_opener)
        except _CURL_TIMEOUT_EXCEPTIONS:
            status = "timeout"
        except _CURL_REQUEST_EXCEPTIONS:
            status = "error"
        except HTTPError as error:
            status = int(error.code)
        except URLError:
            status = "error"
        except TimeoutError:
            status = "timeout"
        if attempt == attempts - 1 or not _should_retry(status):
            return status
        time.sleep(random.uniform(_DELAY_MIN_SECONDS, _DELAY_MAX_SECONDS))
    return status


def _request_status(
    url: str,
    curl_session: object | None,
    urllib_opener: object,
) -> int:
    if curl_session is not None:
        response = curl_session.get(  # type: ignore[union-attr]
            url, timeout=_DEFAULT_TIMEOUT_SECONDS, allow_redirects=True
        )
        return int(response.status_code)
    request = Request(url, method="GET", headers=_DEFAULT_HEADERS)
    with urllib_opener.open(request, timeout=_DEFAULT_TIMEOUT_SECONDS) as response:
        response.read(_RESPONSE_READ_LIMIT)
        return int(getattr(response, "status", 200))


def _should_retry(status: int | str) -> bool:
    if status == "timeout":
        return True
    return isinstance(status, int) and status >= 500


def _page_url_to_check(suggestion: LinkSuggestion) -> str | None:
    if suggestion.verdict == "EXTERNAL-UNCHECKED":
        return None
    if not suggestion.suggested_url:
        return None
    return url_without_fragment(suggestion.suggested_url)


def _apply_status(
    suggestion: LinkSuggestion,
    statuses: dict[str, int | str],
) -> LinkSuggestion:
    page_url = _page_url_to_check(suggestion)
    if page_url is None:
        return suggestion
    status = statuses.get(page_url)
    if status is None:
        return suggestion
    if isinstance(status, int) and 200 <= status < 400:
        note = f"HTTP {status} for {page_url}"
        return replace(suggestion, evidence=_join_evidence(suggestion.evidence, note))
    if status == 403:
        note = f"HTTP 403 inconclusive for {page_url}"
        return replace(
            suggestion,
            confidence="LOW",
            evidence=_join_evidence(suggestion.evidence, note),
        )
    note = f"HTTP {status} for {page_url}"
    return replace(
        suggestion,
        suggested_url="",
        verdict="HTTP-404" if status == 404 else "HTTP-FAILED",
        confidence="HIGH",
        evidence=_join_evidence(suggestion.evidence, note),
    )


def _join_evidence(existing: str, note: str) -> str:
    if not existing:
        return note
    return f"{existing}; {note}"
