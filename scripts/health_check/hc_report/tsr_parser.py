"""Parse TSR HTML exports into structured check records with real statuses."""
from __future__ import annotations

import re
from html import unescape

from hc_report._text import slugify as _slugify

_STATUS_MAP = {
    "PASS": "PASS",
    "FAIL": "FAIL",
    "WARNING": "WARNING",
    "WARN": "WARNING",
    "INFO": "INFO",
    "NA": "NOT_APPLICABLE",
    "NOT_APPLICABLE": "NOT_APPLICABLE",
    "SKIP": "SKIPPED",
    "SKIPPED": "SKIPPED",
}

_SECTION_MAP = [
    ("1. Basic Checks-panel", "2. Topology Checks-btn", "7.1", "Base Platform Checks", "1"),
    ("2. Topology Checks-panel", "3. Component Checks-btn", "7.2", "Topology Checks", "2"),
    ("3. Component Checks-panel", "4. Layered Products-btn", "7.3", "Component Checks", "3"),
    ("4. Layered Products-panel", "5. Cluster Health-btn", "7.4", "Layered Products", "4"),
    ("5. Cluster Health-panel", "6. Day-2 Operations-btn", "7.5", "Cluster Health", "5"),
    ("6. Day-2 Operations-panel", "7. Security and Compliance-btn", "7.6", "Day-2 Operations", "6"),
    ("7. Security and Compliance-panel", "ccx-checks-section-btn", "7.7", "Security and Compliance", "7"),
]

# Per-check Result cap. 2000 chars cut real tables; 1_000_000 hung WeasyPrint
# on production TSR dumps (hundreds of KB in one table cell).
_EVIDENCE_MAX_CHARS = 32_000
_EVIDENCE_TRUNCATION_MARK = "\n… [truncated]"

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\t", " ")
    # Some captured command output (e.g. `oc get storageclass`) is colorized
    # terminal output with raw ANSI SGR escape sequences baked into the TSR
    # HTML (bold/color codes around table headers). These aren't HTML tags
    # so the tag-stripping above never touches them, and left in place they
    # render as literal garbage like `[1mNAME ...[0m` in the final report.
    text = _ANSI_ESCAPE_RE.sub("", text)
    # Some Result cells are pre-formatted fixed-width tables (e.g. `oc get
    # nodes`-style output) using column padding of 3+ spaces, not real HTML
    # <table> markup. A bare `[ \t]+ -> " "` collapse would destroy that
    # alignment (renderer.py needs a 3+ space run to detect column
    # boundaries), but preserving the full original padding width verbatim
    # wastes the evidence buffer (_EVIDENCE_MAX_CHARS) on cosmetic
    # terminal-alignment spaces, which previously pushed real table rows
    # past the truncation cutoff. Normalize any wide gap down to a fixed
    # 3-space marker: the column-boundary signal survives, incidental 1-2
    # space tag-stripping artifacts are left alone, and the byte cost per
    # gap no longer scales with the original column width.
    text = re.sub(r" {3,}", "   ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clip_evidence(text: str) -> str:
    """Keep Result text under the report/PDF budget; mark when truncated."""
    if len(text) <= _EVIDENCE_MAX_CHARS:
        return text
    keep = _EVIDENCE_MAX_CHARS - len(_EVIDENCE_TRUNCATION_MARK)
    return text[:keep] + _EVIDENCE_TRUNCATION_MARK


_NODE_GROUP_HEADER_RE = re.compile(r"[A-Z][A-Z0-9 /._-]* NODES:{2,3}")
_HOST_PREFIX_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*):(.*)$")
_DNS_LETTER_AFTER_DOT_RE = re.compile(r"\.[A-Za-z]")
_OK_BODY_TOKENS = ("[PASS]", "[INFO]")
_NOT_OK_BODY_TOKENS = (
    "[FAIL]",
    "[WARNING]",
    "[WARN]",
    "[LIMITATION]",
    "[SUPPORT LIMITATION]",
    "[SKIP]",
    "[SKIPPED]",
    "[NOT_APPLICABLE]",
    "[NA]",
)
_RESULT_STATUS_TOKENS = _OK_BODY_TOKENS + _NOT_OK_BODY_TOKENS


def _is_section_header(line: str) -> bool:
    return line.endswith("::")


def _is_node_group_header(line: str) -> bool:
    return _NODE_GROUP_HEADER_RE.fullmatch(line) is not None


def _host_name_looks_like_node(host_name: str) -> bool:
    """FQDN with a letter after a dot, or a hyphenated short node name.

    Rejects interface names such as bond0 / bond0.1709 / ipv4.enabled.
    """
    if host_name.count(".") >= 2:
        return _DNS_LETTER_AFTER_DOT_RE.search(host_name) is not None
    if "." in host_name:
        return False
    return "-" in host_name


def _split_host_line(line: str) -> tuple[str, str] | None:
    """Return (hostname-with-colon, remainder) when the line is a host entry."""
    if line.endswith("::"):
        return None
    match = _HOST_PREFIX_RE.fullmatch(line)
    if match is not None:
        host_name = match.group(1)
        if not _host_name_looks_like_node(host_name):
            return None
        return f"{host_name}:", match.group(2).strip()
    if " " in line or "[" in line:
        return None
    if _host_name_looks_like_node(line):
        return f"{line}:", ""
    return None


def _is_host_line(line: str) -> bool:
    return _split_host_line(line) is not None


def _line_has_result_status(line: str) -> bool:
    return any(token in line for token in _RESULT_STATUS_TOKENS)


def _is_field_label(line: str) -> bool:
    """True for a new attribute name (mtu, ipv4.enabled) after host rows."""
    if not line or _is_section_header(line) or _is_host_line(line):
        return False
    return not _line_has_result_status(line)


def _host_body_is_ok(body: str) -> bool:
    if not any(token in body for token in _OK_BODY_TOKENS):
        return False
    return not any(token in body for token in _NOT_OK_BODY_TOKENS)


def _flush_host_block(
    hosts: list[tuple[str, str]],
    preamble: list[str],
    current_host: str | None,
    current_body: list[str],
) -> None:
    body_text = "\n".join(current_body).rstrip()
    if current_host is not None:
        hosts.append((current_host, body_text))
        return
    if current_body:
        preamble.extend(current_body)


def _partition_host_blocks(lines: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    preamble: list[str] = []
    hosts: list[tuple[str, str]] = []
    current_host: str | None = None
    current_body: list[str] = []
    for line in lines:
        parsed_host = _split_host_line(line)
        if parsed_host is not None:
            _flush_host_block(hosts, preamble, current_host, current_body)
            host_label, remainder = parsed_host
            current_host = host_label
            current_body = [remainder] if remainder else []
            continue
        current_body.append(line)
    _flush_host_block(hosts, preamble, current_host, current_body)
    return preamble, hosts


def _append_collapsed_nodes_block(
    output: list[str], group_label: str, body: str, nodes_kind: str
) -> None:
    marker = f"{group_label}::>{nodes_kind}:"
    if body and "\n" not in body:
        output.append(f"{marker}   {body}")
        return
    output.append(marker)
    if body:
        output.extend(body.split("\n"))


def _should_collapse_hosts(hosts: list[tuple[str, str]]) -> bool:
    ok_count = sum(1 for _host_line, body in hosts if _host_body_is_ok(body))
    return ok_count >= 2


def _emit_collapsed_group(
    header: str,
    preamble: list[str],
    hosts: list[tuple[str, str]],
    group_label: str,
) -> list[str]:
    output = [header, *preamble]
    ok_hosts = [(host_line, body) for host_line, body in hosts if _host_body_is_ok(body)]
    not_ok_hosts = [
        (host_line, body) for host_line, body in hosts if not _host_body_is_ok(body)
    ]
    nodes_kind = "ALL NODES" if not not_ok_hosts else "PASS NODES"
    _append_collapsed_nodes_block(output, group_label, ok_hosts[0][1], nodes_kind)
    for host_line, body in not_ok_hosts:
        output.append(host_line)
        if body:
            output.extend(body.split("\n"))
    return output


def _collapse_hosts_in_group(group_label: str, lines: list[str]) -> list[str]:
    if any(">ALL NODES:" in line for line in lines):
        return lines
    if not lines:
        return lines
    header = lines[0]
    preamble, hosts = _partition_host_blocks(lines[1:])
    if not _should_collapse_hosts(hosts):
        return lines
    return _emit_collapsed_group(header, preamble, hosts, group_label)


def _group_end_index(lines: list[str], start: int) -> int:
    end = start + 1
    saw_host = _is_host_line(lines[start])
    while end < len(lines):
        next_line = lines[end]
        if _is_section_header(next_line) or _is_node_group_header(next_line):
            break
        if saw_host and _is_field_label(next_line):
            break
        if _is_host_line(next_line):
            saw_host = True
        end += 1
    return end


def _condense_identical_pass_hosts(text: str) -> str:
    """Collapse identical PASS/INFO host blocks before the evidence clip."""
    if not text:
        return text
    lines = [line.strip() for line in text.split("\n")]
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if _is_node_group_header(line):
            end = _group_end_index(lines, index)
            group_label = line.rstrip(":")
            output.extend(_collapse_hosts_in_group(group_label, lines[index:end]))
            index = end
            continue
        if _is_host_line(line):
            end = _group_end_index(lines, index)
            collapsed = _collapse_hosts_in_group(
                "ALL NODES", ["ALL NODES::", *lines[index:end]]
            )
            if collapsed and collapsed[0] == "ALL NODES::":
                collapsed = collapsed[1:]
            output.extend(collapsed)
            index = end
            continue
        output.append(line)
        index += 1
    return "\n".join(output)


_DOT_HEADER_FIELD_RE = re.compile(r"^[A-Z][A-Z0-9 /._-]*$")


def _is_dot_table_header(line: str) -> bool:
    if " · " not in line:
        return False
    fields = [field.strip() for field in line.split(" · ")]
    return bool(fields) and all(_DOT_HEADER_FIELD_RE.fullmatch(field) for field in fields)


def _is_dot_table_data_row(line: str) -> bool:
    if " · " not in line:
        return False
    if _is_dot_table_header(line):
        return False
    return not _line_has_result_status(line)


def _dot_row_signature(line: str) -> tuple[str, ...]:
    fields = [field.strip() for field in line.split(" · ")]
    if len(fields) >= 3:
        return tuple(fields[2:])
    if len(fields) >= 2:
        return tuple(fields[1:])
    return tuple(fields)


def _emit_dot_table_groups(header: str, rows: list[str]) -> list[str]:
    output = [header] if header else []
    signature_order: list[tuple[str, ...]] = []
    rows_by_signature: dict[tuple[str, ...], list[str]] = {}
    for row in rows:
        signature = _dot_row_signature(row)
        if signature not in rows_by_signature:
            signature_order.append(signature)
            rows_by_signature[signature] = []
        rows_by_signature[signature].append(row)
    for signature in signature_order:
        group_rows = rows_by_signature[signature]
        output.append(group_rows[0])
        extra_count = len(group_rows) - 1
        if extra_count:
            output.append(f"({extra_count} more)")
    return output


def _take_dot_table_data_rows(lines: list[str], start: int) -> tuple[list[str], int]:
    rows: list[str] = []
    index = start
    while index < len(lines):
        next_line = lines[index]
        if _is_dot_table_header(next_line) or not _is_dot_table_data_row(next_line):
            break
        rows.append(next_line)
        index += 1
    return rows, index


def _condense_dot_inventory_tables(text: str) -> str:
    if not text:
        return text
    lines = text.split("\n")
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if _is_dot_table_header(line):
            rows, index = _take_dot_table_data_rows(lines, index + 1)
            if len(rows) < 2:
                output.append(line)
                output.extend(rows)
            else:
                output.extend(_emit_dot_table_groups(line, rows))
            continue
        if _is_dot_table_data_row(line):
            rows, index = _take_dot_table_data_rows(lines, index)
            if len(rows) < 2:
                output.extend(rows)
            else:
                output.extend(_emit_dot_table_groups("", rows))
            continue
        output.append(line)
        index += 1
    return "\n".join(output)


def _condense_result_evidence(text: str) -> str:
    """Chain host then inventory condensation; caller clips."""
    condensed = _condense_identical_pass_hosts(text)
    condensed = _condense_dot_inventory_tables(condensed)
    condensed = _condense_nfs_nconnect_lines(condensed)
    condensed = _condense_repeated_node_status_lines(condensed)
    return _condense_unhealthy_workload_pods(condensed)


_NCONNECT_TOKEN_RE = re.compile(r"\(nconnect=[^)]+\)")
_NODE_STATUS_LINE_RE = re.compile(
    r"^node ([A-Za-z0-9][A-Za-z0-9._-]*)(\s+\w+)?:\s+(.*)$"
)
_NFS_SLOT_SERVICE_TRAILER = "nfs-slot-tuning.service: not active or missing"


def _nconnect_token(line: str) -> str | None:
    match = _NCONNECT_TOKEN_RE.search(line)
    return match.group(0) if match else None


def _condense_nfs_nconnect_lines(text: str) -> str:
    if not text:
        return text
    lines = text.split("\n")
    token_counts: dict[str, int] = {}
    for line in lines:
        token = _nconnect_token(line)
        if token is not None:
            token_counts[token] = token_counts.get(token, 0) + 1
    emitted_tokens: set[str] = set()
    output: list[str] = []
    for line in lines:
        token = _nconnect_token(line)
        if token is None:
            output.append(line)
            continue
        if token in emitted_tokens:
            continue
        emitted_tokens.add(token)
        output.append(line)
        extra_count = token_counts[token] - 1
        if extra_count:
            output.append(f"({extra_count} more NFS mounts with {token})")
    return "\n".join(output)


def _node_status_body(line: str) -> str | None:
    """Return the condensation key for a 'node <host>[<qualifier>]: <status>' line.

    The key includes the qualifier (if any) and a leading separator so that
    the collapsed summary can be emitted as ``(N nodes){key}`` and read
    naturally regardless of whether a qualifier is present.
    """
    if line == _NFS_SLOT_SERVICE_TRAILER:
        return line
    match = _NODE_STATUS_LINE_RE.fullmatch(line)
    if match is None:
        return None
    if not _line_has_result_status(line):
        return None
    qualifier = match.group(2) or ""
    status = match.group(3)
    return f"{qualifier}:   {status}"


def _condense_repeated_node_status_lines(text: str) -> str:
    if not text:
        return text
    lines = text.split("\n")
    body_counts: dict[str, int] = {}
    for line in lines:
        body = _node_status_body(line)
        if body is not None:
            body_counts[body] = body_counts.get(body, 0) + 1
    emitted_bodies: set[str] = set()
    output: list[str] = []
    for line in lines:
        body = _node_status_body(line)
        if body is None:
            output.append(line)
            continue
        if body in emitted_bodies:
            continue
        emitted_bodies.add(body)
        extra_count = body_counts[body] - 1
        if extra_count:
            if body == _NFS_SLOT_SERVICE_TRAILER:
                output.append(f"({extra_count + 1} nodes):   {body}")
            else:
                output.append(f"({extra_count + 1} nodes){body}")
            continue
        output.append(line)
    return "\n".join(output)


_UNHEALTHY_POD_RE = re.compile(r"^([^:\s]+):(\S+)\s+\[WARNING\]\s+- looks unhealthy")
_POD_REPLICA_SUFFIX_RE = re.compile(r"-[a-z0-9]+-[a-z0-9]{5}$")


def _workload_key(line: str) -> str | None:
    match = _UNHEALTHY_POD_RE.match(line)
    if match is None:
        return None
    namespace = match.group(1)
    pod_name = _POD_REPLICA_SUFFIX_RE.sub("", match.group(2))
    return f"{namespace}:{pod_name}"


def _condense_unhealthy_workload_pods(text: str) -> str:
    if not text:
        return text
    lines = text.split("\n")
    workload_counts: dict[str, int] = {}
    for line in lines:
        key = _workload_key(line)
        if key is not None:
            workload_counts[key] = workload_counts.get(key, 0) + 1
    emitted_workloads: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = _workload_key(line)
        if key is None:
            output.append(line)
            continue
        if key in emitted_workloads:
            continue
        emitted_workloads.add(key)
        output.append(line)
        extra_count = workload_counts[key] - 1
        if extra_count:
            output.append(f"({extra_count} more pods)")
    return "\n".join(output)


def _normalize_status(raw: str) -> str:
    return _STATUS_MAP.get(raw.strip().upper(), "SKIPPED")


def _extract_leaf_check(
    leaf_html: str, section_number: str, category_id: str, category_name: str
) -> dict | None:
    """Parse one leaf-extra table block into a check record."""
    status_match = re.search(r">Status</td>\s*<td[^>]*>\s*<b>(\w+)</b>", leaf_html, re.I)
    if not status_match:
        return None

    status = _normalize_status(status_match.group(1))

    check_match = re.search(
        r">Check</td>\s*<td[^>]*>(.*?)</td>", leaf_html, re.S | re.I
    )
    title = ""
    context = ""
    if check_match:
        raw_check = check_match.group(1)
        context_match = re.search(r"<p>(.*?)</p>", raw_check, re.S)
        if context_match:
            context = _strip_html(context_match.group(1))
        title_part = re.sub(r"<p>.*?</p>", "", raw_check, flags=re.S)
        title = _strip_html(title_part)

    if not title:
        return None

    tags: list[str] = []
    tags_match = re.search(r">Tags</td>\s*<td[^>]*>(.*?)</td>", leaf_html, re.S | re.I)
    if tags_match:
        for badge in re.findall(r'av-tag-badge["\s>]*>([^<]+)', tags_match.group(1)):
            cleaned = badge.strip().lower()
            if cleaned:
                tags.append(cleaned)

    evidence = ""
    result_match = re.search(r">Result</td>\s*<td[^>]*>(.*?)</td>", leaf_html, re.S | re.I)
    if result_match:
        evidence = _clip_evidence(
            _condense_result_evidence(_strip_html(result_match.group(1)))
        )

    ref_match = re.match(r"^(\d+(?:\.\d+)*)", title)
    tsr_ref = ref_match.group(1) if ref_match else section_number

    return {
        "check_id": f"{category_id}.tsr.{_slugify(title)}",
        "title": title,
        "section": int(section_number),
        "category_id": category_id,
        "category_name": category_name,
        "source": "tsr",
        "status": status,
        "evidence": evidence,
        "tags": tags,
        "context": context,
        "tsr_ref": tsr_ref,
    }


def _parse_sections(html: str) -> list[dict]:
    """Extract leaf-level checks from TSR sections 1-7."""
    results: list[dict] = []
    seen_ids: set[str] = set()

    for panel_id, next_btn, category_id, category_name, section_number in _SECTION_MAP:
        start = html.find(f'id="{panel_id}"')
        if start < 0:
            continue
        end = html.find(f'id="{next_btn}"', start)
        if end < 0:
            end = len(html)
        section = html[start:end]

        leaves = section.split('<div class="leaf-extra"')
        for leaf_raw in leaves[1:]:
            close_index = leaf_raw.find("</div>\n                </div>\n")
            if close_index < 0:
                close_index = min(len(leaf_raw), 10000)
            leaf_block = leaf_raw[:close_index]

            record = _extract_leaf_check(leaf_block, section_number, category_id, category_name)
            if record and record["check_id"] not in seen_ids:
                seen_ids.add(record["check_id"])
                results.append(record)

    return results


def _parse_ccx_section(html: str) -> list[dict]:
    """Extract CCX advisory checks from the ccx-checks-section."""
    ccx_start = html.find('id="ccx-checks-section-panel"')
    if ccx_start < 0:
        return []
    ccx_end = html.find('id="escalations-btn"', ccx_start)
    if ccx_end < 0:
        ccx_end = len(html)
    ccx_section = html[ccx_start:ccx_end]

    group_ranges = [
        ("external", 'id="External-panel"', 'id="Internal-btn"'),
        ("internal", 'id="Internal-panel"', 'id="Skips-btn"'),
        ("skip", 'id="Skips-panel"', None),
    ]

    results: list[dict] = []
    seen_ids: set[str] = set()

    for group, start_marker, end_marker in group_ranges:
        group_start = ccx_section.find(start_marker)
        if group_start < 0:
            continue
        group_end = ccx_section.find(end_marker, group_start) if end_marker else len(ccx_section)
        if group_end < 0:
            group_end = len(ccx_section)
        group_section = ccx_section[group_start:group_end]

        for part in group_section.split("<b>Check:</b>")[1:]:
            record = _extract_ccx_check(part[:8000], group)
            if record and record["check_id"] not in seen_ids:
                seen_ids.add(record["check_id"])
                results.append(record)

    return results


def _extract_ccx_check(chunk: str, group: str) -> dict | None:
    """Parse one CCX check entry from its HTML fragment."""
    title_raw = chunk.split("<br", 1)[0]
    title = _strip_html(title_raw)
    if not title:
        return None

    status_match = re.search(r"<b>Status:</b>\s*([^<\n]+)", chunk, re.I)
    status = _normalize_status(status_match.group(1).strip() if status_match else "skip")

    tags = []
    for badge in re.findall(r"border-radius:1rem[^>]*>([^<]+)</span>", chunk):
        cleaned = _strip_html(badge).lower()
        if cleaned:
            tags.append(cleaned)

    evidence = ""
    message_match = re.search(r"<b>Message:</b>\s*(.*?)(?:</td>|$)", chunk, re.S)
    if message_match:
        evidence = _clip_evidence(_strip_html(message_match.group(1)))

    check_id = f"7.7.ccx_{group}.{_slugify(title)}"
    return {
        "check_id": check_id,
        "title": title,
        "section": 8,
        "category_id": "7.7",
        "category_name": "Security and Compliance",
        "source": "ccx",
        "group": group,
        "status": status,
        "evidence": evidence,
        "tags": tags,
        "context": "",
        "tsr_ref": f"CCX:{group}",
    }


def parse_tsr_html(html: str) -> list[dict]:
    """Parse a TSR HTML export into a flat list of check records."""
    checks = _parse_sections(html)
    checks.extend(_parse_ccx_section(html))
    return checks
