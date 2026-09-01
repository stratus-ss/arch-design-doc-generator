"""Evaluators for 7.8 Performance Metrics."""
from __future__ import annotations

import math

from hc_report.evaluators._common import (
    _is_missing,
    _not_applicable,
    _parse_prometheus_vector,
    _prometheus_value,
)
from hc_report.models import CheckResult


def _build_node_map(data: dict, label_key: str = "node") -> dict[str, float]:
    result: dict[str, float] = {}
    for item in _parse_prometheus_vector(data):
        node = item.get("metric", {}).get(label_key, "unknown")
        try:
            result[node] = float(item.get("value", [0, 0])[1])
        except (TypeError, ValueError, IndexError):
            pass
    return result


def _evaluate_prometheus_node_metrics(
    cpu_req: dict, mem_req: dict, cpu_lim: dict, mem_lim: dict,
    mem_wss: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    """Node CPU and memory request/limit allocations from Prometheus."""
    cpu_req_map = _build_node_map(cpu_req)
    mem_req_map = _build_node_map(mem_req)
    cpu_lim_map = _build_node_map(cpu_lim)
    mem_lim_map = _build_node_map(mem_lim)
    mem_wss_map = _build_node_map(mem_wss)

    all_nodes = set(cpu_req_map) | set(mem_req_map) | set(mem_wss_map)
    if not all_nodes:
        return [_not_applicable(f"{category_id}.node_alloc", "Node Resource Allocation", category_id, category_name,
                    "Prometheus metrics not available")]

    checks = []
    for node in sorted(all_nodes):
        short = node.split(".")[0]
        metrics = {
            "cpu_req": cpu_req_map.get(node),
            "mem_req": mem_req_map.get(node),
            "cpu_lim": cpu_lim_map.get(node),
            "mem_lim": mem_lim_map.get(node),
            "mem_wss": mem_wss_map.get(node),
        }
        checks.append(_build_node_alloc_check(node, short, metrics, category_id, category_name))
    return checks


def _build_node_alloc_check(
    node: str, short: str, node_metrics: dict, category_id: str, category_name: str,
) -> CheckResult:
    parts = []
    if node_metrics["cpu_req"] is not None:
        parts.append(f"CPU requests: {node_metrics['cpu_req']:.0f}%")
    if node_metrics["cpu_lim"] is not None:
        parts.append(f"limits: {node_metrics['cpu_lim']:.0f}%")
    if node_metrics["mem_req"] is not None:
        parts.append(f"Mem requests: {node_metrics['mem_req']:.0f}%")
    if node_metrics["mem_lim"] is not None:
        parts.append(f"limits: {node_metrics['mem_lim']:.0f}%")
    if node_metrics["mem_wss"] is not None:
        parts.append(f"working set: {node_metrics['mem_wss']:.0f}%")

    issues = []
    if node_metrics["cpu_req"] is not None and node_metrics["cpu_req"] > 90:
        issues.append(f"CPU requests critically high ({node_metrics['cpu_req']:.0f}%)")
    if node_metrics["mem_req"] is not None and node_metrics["mem_req"] > 90:
        issues.append(f"Memory requests critically high ({node_metrics['mem_req']:.0f}%)")
    if node_metrics["mem_wss"] is not None and node_metrics["mem_wss"] > 85:
        issues.append(f"Memory working set high ({node_metrics['mem_wss']:.0f}%)")

    status = "WARNING" if issues else "PASS"
    evidence = ". ".join(parts) if parts else "No metrics available"
    if issues:
        evidence += ". ALERT: " + "; ".join(issues)

    return CheckResult(category_id, category_name, f"{category_id}.node.{short}.alloc",
                       f"7.8.1 Node Resource Allocation: {short}", status, evidence, node)


# ---------------------------------------------------------------------------
# etcd performance — split into one function per metric
# ---------------------------------------------------------------------------

def _evaluate_etcd_wal_fsync(wal_fsync: dict, category_id: str, category_name: str) -> list[CheckResult]:
    results = _parse_prometheus_vector(wal_fsync)
    if not results:
        return [_not_applicable(f"{category_id}.etcd.wal", "7.8.2 Etcd WAL fsync P99",
                    category_id, category_name, "Prometheus metric not available")]
    checks = []
    for item in results:
        pod = item.get("metric", {}).get("pod", "unknown")
        latency_ms = _prometheus_milliseconds(item)
        if latency_ms is None:
            continue
        if latency_ms > WAL_P99_FAIL_MILLISECONDS:
            status, note = "FAIL", f"{latency_ms:.1f}ms P99 WAL fsync (documented FAIL bar {WAL_P99_FAIL_MILLISECONDS:.0f}ms)"
        else:
            status, note = "PASS", f"{latency_ms:.2f}ms P99 WAL fsync — within healthy range (<{WAL_P99_FAIL_MILLISECONDS:.0f}ms)"
        checks.append(CheckResult(
            category_id, category_name, f"{category_id}.etcd.wal.{pod}",
            f"7.8.2 Etcd WAL fsync P99: {pod}", status, note, pod,
            scoring_basis="doc_backed" if status == "FAIL" else "",
        ))
    return checks


BACKEND_COMMIT_INFO_MILLISECONDS = 25.0


def _evaluate_etcd_backend_commit(backend_commit: dict, category_id: str, category_name: str) -> list[CheckResult]:
    results = _parse_prometheus_vector(backend_commit)
    if not results:
        return []
    checks = []
    for item in results:
        pod = item.get("metric", {}).get("pod", "unknown")
        latency_ms = _prometheus_milliseconds(item)
        if latency_ms is None:
            continue
        if latency_ms > BACKEND_COMMIT_INFO_MILLISECONDS:
            status, note = (
                "INFO",
                f"{latency_ms:.1f}ms P99 backend commit — 4.22 HTML does not give a FAIL bar for backend commit P99",
            )
        else:
            status, note = "PASS", f"{latency_ms:.2f}ms P99 backend commit — within healthy range (<{BACKEND_COMMIT_INFO_MILLISECONDS:.0f}ms)"
        checks.append(CheckResult(category_id, category_name, f"{category_id}.etcd.backend.{pod}",
                                  f"7.8.3 Etcd Backend Commit P99: {pod}", status, note, pod))
    return checks


def _evaluate_etcd_leader_changes(leader_changes: dict, category_id: str, category_name: str) -> list[CheckResult]:
    leader_results = _parse_prometheus_vector(leader_changes)
    if not leader_results:
        return [_not_applicable(f"{category_id}.etcd.leader", "7.8.4 Etcd Leader Stability", category_id, category_name)]
    total_changes = sum(
        float(result_item.get("value", [0, 0])[1]) for result_item in leader_results if result_item.get("value")
    )
    if total_changes > 3:
        status, note = "WARNING", f"{total_changes:.0f} leader election(s) in the last hour — possible instability"
    elif total_changes > 0:
        status, note = "INFO", f"{total_changes:.0f} leader election(s) in the last hour — acceptable"
    else:
        status, note = "PASS", "No leader elections in the last hour — etcd leader stable"
    return [CheckResult(category_id, category_name, f"{category_id}.etcd.leader_changes",
                        "7.8.4 Etcd Leader Stability", status, note, "etcd")]


def _evaluate_etcd_db_size(db_size: dict, db_used: dict, category_id: str, category_name: str) -> list[CheckResult]:
    size_results = _parse_prometheus_vector(db_size)
    used_results = _parse_prometheus_vector(db_used)
    if not size_results:
        return []
    checks = []
    for item in size_results:
        pod = item.get("metric", {}).get("pod", "unknown")
        try:
            size_mib = float(item.get("value", [0, 0])[1]) / (1024 ** 2)
        except (TypeError, ValueError, IndexError):
            continue
        used_item = None
        for result_item in used_results:
            if result_item.get("metric", {}).get("pod") == pod:
                used_item = result_item
                break
        used_mib = 0.0
        if used_item:
            try:
                used_mib = float(used_item.get("value", [0, 0])[1]) / (1024 ** 2)
            except (TypeError, ValueError, IndexError):
                pass
        if size_mib > 8192:
            status = "FAIL"
            note = f"DB size {size_mib:.0f} MiB — exceeds 8 GiB critical threshold. Compaction required"
        elif size_mib > 4096:
            status = "WARNING"
            note = f"DB size {size_mib:.0f} MiB — approaching 8 GiB limit. Monitor and compact if needed"
        else:
            status = "PASS"
            note = f"DB size: {size_mib:.0f} MiB (in-use: {used_mib:.0f} MiB). Well below 8 GiB limit"
        checks.append(CheckResult(category_id, category_name, f"{category_id}.etcd.db.{pod}",
                                  f"7.8.5 Etcd DB Size: {pod}", status, note, pod))
    return checks


DEFRAG_FAIL_RATIO = 0.70
DEFRAG_WARNING_RATIO = 0.50


def _etcd_member_byte_map(vector: dict) -> dict[str, float]:
    members: dict[str, float] = {}
    for item in _parse_prometheus_vector(vector):
        pod_name = item.get("metric", {}).get("pod", "unknown")
        byte_count = _prometheus_value(item)
        if math.isnan(byte_count) or math.isinf(byte_count):
            continue
        members[pod_name] = byte_count
    return members


def _etcd_fragment_ratios(
    size_by_pod: dict[str, float], used_by_pod: dict[str, float],
) -> dict[str, float]:
    ratios: dict[str, float] = {}
    for pod_name, size_bytes in size_by_pod.items():
        if size_bytes <= 0 or pod_name not in used_by_pod:
            continue
        used_bytes = used_by_pod[pod_name]
        ratios[pod_name] = (size_bytes - used_bytes) / size_bytes
    return ratios


def _etcd_defrag_status(ratios: dict[str, float]) -> tuple[str, str]:
    worst_pod = max(ratios, key=ratios.get)
    max_ratio = ratios[worst_pod]
    evidence = (
        f"max fragment ratio {max_ratio:.2f} on {worst_pod}; "
        + "; ".join(f"{name}={ratio:.2f}" for name, ratio in sorted(ratios.items()))
    )
    if max_ratio >= DEFRAG_FAIL_RATIO:
        return "FAIL", evidence
    if max_ratio >= DEFRAG_WARNING_RATIO:
        return "WARNING", evidence
    return "PASS", evidence


def _evaluate_etcd_defrag(
    db_size: dict, db_used: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.etcd.defrag"
    title = "etcd fragmentation"
    if _is_missing(db_size) and _is_missing(db_used):
        return [CheckResult(
            category_id, category_name, check_id, title, "SKIPPED",
            "etcd_db_size_bytes and etcd_db_size_in_use missing", "etcd",
        )]
    ratios = _etcd_fragment_ratios(
        _etcd_member_byte_map(db_size),
        _etcd_member_byte_map(db_used),
    )
    if not ratios:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "No matching etcd size and in-use samples", "etcd",
        )]
    status, evidence = _etcd_defrag_status(ratios)
    return [CheckResult(
        category_id, category_name, check_id, title, status, evidence, "etcd",
    )]


def _evaluate_etcd_proposals(proposals_failed: dict, category_id: str, category_name: str) -> list[CheckResult]:
    prop_results = _parse_prometheus_vector(proposals_failed)
    if not prop_results:
        return []
    total_failed = sum(float(result_item.get("value", [0, 0])[1]) for result_item in prop_results if result_item.get("value"))
    if total_failed > 0:
        return [CheckResult(category_id, category_name, f"{category_id}.etcd.proposals",
                            "7.8.6 Etcd Failed Proposals", "WARNING",
                            f"{total_failed:.0f} failed proposal(s) in last hour — indicates raft instability",
                            "etcd")]
    return [CheckResult(category_id, category_name, f"{category_id}.etcd.proposals",
                        "7.8.6 Etcd Failed Proposals", "PASS",
                        "No failed raft proposals in the last hour", "etcd")]


WAL_P99_FAIL_MILLISECONDS = 10.0
COMPACTION_WARNING_MILLISECONDS = 200.0
COMPACTION_FAIL_MILLISECONDS = 900.0


def _prometheus_milliseconds(item: dict) -> float | None:
    try:
        seconds = float(item.get("value", [0, 0])[1])
    except (TypeError, ValueError, IndexError):
        return None
    if math.isnan(seconds) or math.isinf(seconds):
        return None
    return seconds * 1000.0


def _automatic_compaction_flags_from_pods(etcd_pods: dict) -> str:
    snippets: list[str] = []
    for pod in etcd_pods.get("items") or []:
        pod_name = (pod.get("metadata") or {}).get("name", "unknown")
        spec = pod.get("spec") or {}
        for container in spec.get("containers") or []:
            fragments: list[str] = []
            for part in list(container.get("command") or []) + list(container.get("args") or []):
                text = str(part)
                lowered = text.lower()
                if "auto-compaction" in lowered or "auto_compaction" in lowered:
                    fragments.append(text)
            for env in container.get("env") or []:
                name = str(env.get("name") or "")
                value = str(env.get("value") or "")
                joined = f"{name}={value}"
                lowered_joined = joined.lower()
                if "auto-compaction" in lowered_joined or "auto_compaction" in lowered_joined:
                    fragments.append(joined)
            if fragments:
                snippets.append(f"{pod_name}: {' '.join(fragments)}")
    if not snippets:
        return "none"
    return "; ".join(snippets)


def _evaluate_etcd_disk_aggregate(
    wal_fsync: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    latencies_ms: list[float] = []
    for item in _parse_prometheus_vector(wal_fsync):
        milliseconds = _prometheus_milliseconds(item)
        if milliseconds is not None:
            latencies_ms.append(milliseconds)
    check_id = f"{category_id}.etcd.disk"
    title = "7.8 etcd disk aggregate (WAL P99)"
    if not latencies_ms:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "No WAL samples", "etcd",
        )]
    max_ms = max(latencies_ms)
    if max_ms > WAL_P99_FAIL_MILLISECONDS:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"WAL P99 max {max_ms:.1f}ms exceeds {WAL_P99_FAIL_MILLISECONDS:.0f}ms",
            "etcd", scoring_basis="doc_backed",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"WAL P99 max {max_ms:.2f}ms — all members at or below {WAL_P99_FAIL_MILLISECONDS:.0f}ms",
        "etcd",
    )]


def _evaluate_etcd_compaction(
    compaction_data: dict, etcd_pods: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    flag_snippet = _automatic_compaction_flags_from_pods(etcd_pods)
    check_id = f"{category_id}.etcd.compaction"
    title = "7.8 etcd compaction p95"
    samples_ms: list[float] = []
    for item in _parse_prometheus_vector(compaction_data):
        milliseconds = _prometheus_milliseconds(item)
        if milliseconds is not None:
            samples_ms.append(milliseconds)
    evidence_suffix = f" auto-compaction flags: {flag_snippet}"
    if not samples_ms:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            f"Compaction metric missing or NaN.{evidence_suffix}", "etcd",
        )]
    max_ms = max(samples_ms)
    if max_ms > COMPACTION_FAIL_MILLISECONDS:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"compaction p95 max {max_ms:.1f}ms exceeds {COMPACTION_FAIL_MILLISECONDS:.0f}ms.{evidence_suffix}",
            "etcd", scoring_basis="doc_backed",
        )]
    if max_ms > COMPACTION_WARNING_MILLISECONDS:
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"compaction p95 max {max_ms:.1f}ms above {COMPACTION_WARNING_MILLISECONDS:.0f}ms.{evidence_suffix}",
            "etcd",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        f"compaction p95 max {max_ms:.2f}ms — at or below {COMPACTION_WARNING_MILLISECONDS:.0f}ms.{evidence_suffix}",
        "etcd",
    )]


def _evaluate_etcd_log_errors(
    log_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.etcd.log_errors"
    title = "7.8 etcd log phrase errors (6h)"
    members = log_data.get("members") or []
    phrase_total = 0
    unreadable = bool(log_data.get("_hc_error"))
    for member in members:
        if member.get("_hc_error"):
            unreadable = True
        phrase_total += int(member.get("heartbeat") or 0)
        phrase_total += int(member.get("timed_out") or 0)
        phrase_total += int(member.get("rafthttp") or 0)
    if phrase_total > 0:
        return [CheckResult(
            category_id, category_name, check_id, title, "FAIL",
            f"log phrase counts in 6h sum to {phrase_total}", "etcd",
        )]
    if unreadable or not members:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "Logs unreadable or log-phrase collect missing", "etcd",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        "All three phrase counts are 0 over 6h", "etcd",
    )]


def _evaluate_etcd_heartbeat(
    heartbeat_data: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    check_id = f"{category_id}.etcd.heartbeat"
    title = "7.8 etcd heartbeat send failures (1h)"
    samples = _parse_prometheus_vector(heartbeat_data)
    if not samples:
        return [CheckResult(
            category_id, category_name, check_id, title, "INFO",
            "Heartbeat metric missing", "etcd",
        )]
    total_increase = 0.0
    for item in samples:
        increase = _prometheus_value(item)
        if math.isnan(increase) or math.isinf(increase):
            return [CheckResult(
                category_id, category_name, check_id, title, "INFO",
                "Heartbeat metric missing", "etcd",
            )]
        total_increase += increase
    if total_increase > 0:
        return [CheckResult(
            category_id, category_name, check_id, title, "WARNING",
            f"heartbeat send-failure increase {total_increase:.0f} over 1h", "etcd",
        )]
    return [CheckResult(
        category_id, category_name, check_id, title, "PASS",
        "heartbeat send-failure increase is 0 over 1h", "etcd",
    )]


def _evaluate_etcd_performance(
    wal_fsync: dict, backend_commit: dict, leader_changes: dict,
    db_size: dict, db_used: dict, proposals_failed: dict,
    heartbeat_failures: dict, category_id: str, category_name: str,
) -> list[CheckResult]:
    """Aggregate all etcd performance metric checks."""
    checks: list[CheckResult] = []
    checks += _evaluate_etcd_wal_fsync(wal_fsync, category_id, category_name)
    checks += _evaluate_etcd_disk_aggregate(wal_fsync, category_id, category_name)
    checks += _evaluate_etcd_backend_commit(backend_commit, category_id, category_name)
    checks += _evaluate_etcd_leader_changes(leader_changes, category_id, category_name)
    checks += _evaluate_etcd_db_size(db_size, db_used, category_id, category_name)
    checks += _evaluate_etcd_defrag(db_size, db_used, category_id, category_name)
    checks += _evaluate_etcd_proposals(proposals_failed, category_id, category_name)
    checks += _evaluate_etcd_heartbeat(heartbeat_failures, category_id, category_name)
    return checks


def _evaluate_apiserver_latency(latency_data: dict, error_rate_data: dict,
                              category_id: str, category_name: str) -> list[CheckResult]:
    """API server P99 latency and error rate."""
    checks = []
    latency_results = _parse_prometheus_vector(latency_data)
    if latency_results:
        max_latency_ms = 0.0
        max_label = ""
        for item in latency_results:
            sample_latency_ms = _prometheus_value(item) * 1000
            if sample_latency_ms > max_latency_ms:
                max_latency_ms = sample_latency_ms
                resource = item.get("metric", {}).get("resource", "")
                verb = item.get("metric", {}).get("verb", "")
                max_label = f"{verb} {resource}"

        if max_latency_ms > 1000:
            status = "FAIL"
            evidence = f"P99 API latency {max_latency_ms:.0f}ms for {max_label} — exceeds 1s critical threshold"
        elif max_latency_ms > 500:
            status = "WARNING"
            evidence = f"P99 API latency {max_latency_ms:.0f}ms for {max_label} — exceeds 500ms recommendation"
        else:
            status = "PASS"
            evidence = f"P99 API latency: max {max_latency_ms:.0f}ms — within acceptable range (<500ms)"
        checks.append(CheckResult(category_id, category_name, f"{category_id}.apiserver.latency",
                                  "7.8.7 API Server Request Latency P99", status, evidence, "apiserver"))
    else:
        checks.append(_not_applicable(f"{category_id}.apiserver.latency",
                          "7.8.7 API Server Request Latency P99", category_id, category_name))

    error_results = _parse_prometheus_vector(error_rate_data)
    if error_results:
        total_rate = sum(
            float(result_item.get("value", [0, 0])[1]) for result_item in error_results if result_item.get("value")
        )
        if total_rate > 1.0:
            status = "WARNING"
            evidence = f"API server 5xx error rate: {total_rate:.2f} req/s — investigate apiserver logs"
        else:
            status = "PASS"
            evidence = f"API server 5xx error rate: {total_rate:.3f} req/s — within acceptable range"
        checks.append(CheckResult(category_id, category_name, f"{category_id}.apiserver.errors",
                                  "7.8.8 API Server Error Rate", status, evidence, "apiserver"))
    return checks


def _parse_json_array_output(data: dict) -> list:
    """Parse the JSON array embedded in a captured CLI `output` field, or [] if absent/invalid."""
    text = data.get("output", "")
    try:
        return [] if not text.strip().startswith("[") else __import__("json").loads(text)
    except (ValueError, AttributeError):
        return []


def _check_etcd_endpoint_health(health_data: dict, category_id: str, category_name: str) -> CheckResult | None:
    if not health_data or health_data.get("_hc_error"):
        return None
    health_items = _parse_json_array_output(health_data)
    if not health_items:
        return None
    unhealthy = [endpoint for endpoint in health_items if not endpoint.get("health")]
    if unhealthy:
        return CheckResult(category_id, category_name, f"{category_id}.etcd.endpoint_health",
                            "7.8.9 Etcd Endpoint Health", "FAIL",
                            f"{len(unhealthy)}/{len(health_items)} endpoints unhealthy: "
                            f"{[endpoint.get('endpoint') for endpoint in unhealthy]}", "etcd")
    return CheckResult(category_id, category_name, f"{category_id}.etcd.endpoint_health",
                        "7.8.9 Etcd Endpoint Health", "PASS",
                        f"All {len(health_items)} etcd endpoints healthy", "etcd")


def _check_etcd_endpoint_dbsize(status_data: dict, category_id: str, category_name: str) -> CheckResult | None:
    if not status_data or status_data.get("_hc_error"):
        return None
    status_items = _parse_json_array_output(status_data)
    if not status_items:
        return None
    db_sizes = []
    for endpoint in status_items:
        status = endpoint.get("status", {})
        db_sizes.append(str(round(status.get("dbSize", 0) / (1024 ** 2))) + "MiB")
    return CheckResult(category_id, category_name, f"{category_id}.etcd.endpoint_status",
                        "7.8.10 Etcd Endpoint Status",
                        "PASS" if len(status_items) == 3 else "WARNING",
                        f"{len(status_items)} member(s). DB sizes: {db_sizes}", "etcd")


def _evaluate_etcd_endpoint_status(health_data: dict, status_data: dict,
                                 category_id: str, category_name: str) -> list[CheckResult]:
    """etcd endpoint health and status from etcdctl."""
    checks = []
    health_check = _check_etcd_endpoint_health(health_data, category_id, category_name)
    if health_check:
        checks.append(health_check)
    dbsize_check = _check_etcd_endpoint_dbsize(status_data, category_id, category_name)
    if dbsize_check:
        checks.append(dbsize_check)
    return checks


def _evaluate_pvc_utilization(pvc_util_data: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """PVC utilization % from Prometheus kubelet metrics."""
    results = _parse_prometheus_vector(pvc_util_data)
    if not results:
        return [_not_applicable(f"{category_id}.pvc_util", "PVC Utilization", category_id, category_name,
                    "kubelet volume metrics not available")]

    critical, warning, healthy = [], [], []
    for item in results:
        node_metrics = item.get("metric", {})
        pvc_name = node_metrics.get("persistentvolumeclaim", node_metrics.get("namespace", "unknown"))
        namespace = node_metrics.get("namespace", "")
        try:
            pct = float(item.get("value", [0, 0])[1])
        except (TypeError, ValueError, IndexError):
            continue
        label = f"{namespace}/{pvc_name}" if namespace else pvc_name
        if pct > 90:
            critical.append(f"{label}: {pct:.0f}%")
        elif pct > 75:
            warning.append(f"{label}: {pct:.0f}%")
        else:
            healthy.append(f"{label}: {pct:.0f}%")

    checks: list[CheckResult] = []
    if critical:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.pvc.util.critical",
                                  "7.8.11 PVC Utilization (Critical)", "FAIL",
                                  f"{len(critical)} PVC(s) >90% full: {'; '.join(critical[:5])}",
                                  "pvc"))
    if warning:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.pvc.util.warning",
                                  "7.8.12 PVC Utilization (Warning)", "WARNING",
                                  f"{len(warning)} PVC(s) 75–90% full: {'; '.join(warning[:5])}",
                                  "pvc"))
    if healthy and not critical and not warning:
        checks.append(CheckResult(category_id, category_name, f"{category_id}.pvc.util.ok",
                                  "7.8.11 PVC Utilization", "PASS",
                                  f"All {len(healthy)} monitored PVC(s) below 75% utilization",
                                  "pvc"))
    return checks or [_not_applicable(f"{category_id}.pvc_util", "PVC Utilization", category_id, category_name)]


def evaluate_metrics(category_data: dict, results: dict, category_id: str, category_name: str) -> list[CheckResult]:
    """Dispatch evaluators for 7.8 Performance Metrics."""
    checks: list[CheckResult] = []
    checks += _evaluate_prometheus_node_metrics(
        category_data.get("node_cpu_requests_pct", {}),
        category_data.get("node_memory_requests_pct", {}),
        category_data.get("node_cpu_limits_pct", {}),
        category_data.get("node_memory_limits_pct", {}),
        category_data.get("node_memory_working_set_pct", {}),
        category_id, category_name,
    )
    checks += _evaluate_etcd_performance(
        category_data.get("etcd_disk_wal_fsync_p99", {}),
        category_data.get("etcd_disk_backend_p99", {}),
        category_data.get("etcd_leader_changes_1h", {}),
        category_data.get("etcd_db_size_bytes", {}),
        category_data.get("etcd_db_size_in_use", {}),
        category_data.get("etcd_proposals_failed", {}),
        category_data.get("etcd_heartbeat_failures", {}),
        category_id, category_name,
    )
    checks += _evaluate_etcd_compaction(
        category_data.get("etcd_compaction_p95", {}),
        results.get("05_components", {}).get("etcd_pods", {}),
        category_id, category_name,
    )
    checks += _evaluate_etcd_log_errors(
        category_data.get("etcd_log_phrase_counts", {}),
        category_id, category_name,
    )
    checks += _evaluate_apiserver_latency(
        category_data.get("apiserver_request_latency_p99", {}),
        category_data.get("apiserver_error_rate", {}),
        category_id, category_name,
    )
    checks += _evaluate_etcd_endpoint_status(
        category_data.get("etcd_endpoint_health", {}),
        category_data.get("etcd_endpoint_status", {}),
        category_id, category_name,
    )
    checks += _evaluate_pvc_utilization(category_data.get("pvc_utilization_pct", {}), category_id, category_name)
    return checks
