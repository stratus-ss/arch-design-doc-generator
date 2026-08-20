"""Static best-practice notes keyed on check_id substring."""
from __future__ import annotations

from hc_report.kb_loader import _resolve_default_doc_link, load_kb, resolve_version

_CHECK_NOTES: dict[str, tuple[str, str]] = {
    "identity.channel": (
        "The update channel determines which OCP releases are offered as updates. "
        "For production clusters `stable-X.Y` is recommended. `fast` receives updates 2–4 weeks earlier "
        "but with less soak time. `eus` (Even Update Support) channels allow skipping minor versions.",
        "[Update channels docs](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/updating_clusters/index#fast-stable-channel-strategies_understanding-update-channels-releases)",
    ),
    "identity.updates": (
        "Red Hat recommends keeping OCP within 2 minor versions of the latest release on the selected "
        "channel. Delaying updates increases exposure to security vulnerabilities and reduces supportability.",
        "[Updating OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/updating_clusters/index#upgrade-version-paths_understanding-update-channels-releases)",
    ),
    "infra.topology": (
        "Highly Available (HA) topology requires a minimum of 3 control plane nodes and ensures that the "
        "loss of any single node does not cause an outage. SingleReplica topology (SNO) is only "
        "supported for edge/test deployments.",
        "[Planning your installation](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/architecture/index#control-plane)",
    ),
    "node.ready": (
        "All nodes must be in Ready state for the cluster to operate normally. A Not Ready condition "
        "typically indicates a network, runtime, or kubelet issue. Investigate with `oc describe node <name>`.",
        "[Node management](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/nodes/index#nodes-nodes-working)",
    ),
    "node.cpu": (
        "Red Hat recommends at least 4 cores for control plane nodes and 2 cores for worker nodes. "
        "As cluster workload grows, control plane nodes may need resizing. "
        "See 'Control plane node sizing' in the scalability documentation.",
        "[Node sizing](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/scalability_and_performance/index#master-node-sizing_recommended-control-plane-practices)",
    ),
    "node.memory": (
        "Control plane nodes require at least 16 GiB RAM, workers 8 GiB. "
        "`systemReserved` should be set appropriately for the total node memory — "
        "inadequate system reservation can cause OOM events on the kubelet.",
        "[System reserved resources](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/installing_on_any_platform/index#installation-minimum-resource-requirements_installing-platform-agnostic)",
    ),
    "node.sysreserved": (
        "For nodes with 64 GiB+ RAM, Red Hat recommends setting systemReserved memory to at least "
        "1–2 GiB via KubeletConfig. Insufficient systemReserved can cause the kubelet itself to be "
        "OOM-killed during memory pressure events.",
        "[KubeletConfig](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/nodes/index#nodes-nodes-resources-configuring-setting_nodes-nodes-resources-configuring)",
    ),
    "node.disk": (
        "The recommended minimum disk size is 120 GiB for the primary partition. "
        "For etcd workloads, consider a dedicated `/var/lib/etcd` partition. "
        "etcd is sensitive to disk latency — SSD or NVMe storage is strongly recommended.",
        "[Recommended practices for scaling](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/installing_on_any_platform/index#installation-minimum-resource-requirements_installing-platform-agnostic)",
    ),
    "node.kubelet": (
        "Kubelet version must match the OCP release. Version skew between the cluster version and node "
        "kubelet typically indicates a node that has not completed the machine config update rollout.",
        "[MachineConfig updates](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/updating_clusters/index#machine-config-operator-node-updates_openshift-update-duration)",
    ),
    "node.utilization": (
        "Node CPU utilization above 80% or memory above 85% warrants investigation. "
        "High sustained utilization may indicate the need for additional nodes or workload redistribution. "
        "For control plane nodes, high utilization can degrade API response times.",
        "[Monitoring](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/nodes/index#nodes-nodes-viewing-memory_nodes-nodes-viewing)",
    ),
    "mcp.": (
        "The MachineConfigPool manages the operating system configuration for nodes. "
        "All nodes should be in the `Updated` state (not `Updating` or `Degraded`). "
        "A degraded MCP may indicate a failed machine config rollout.",
        "[MachineConfigPool](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/machine_configuration/index#checking-mco-status_machine-config-overview)",
    ),
    "etcd.members": (
        "etcd requires a quorum of (n/2)+1 members to operate. A 3-member etcd cluster tolerates the loss "
        "of 1 member. Degraded etcd members must be investigated immediately as data loss can occur. "
        "Run `oc get etcd cluster -o yaml` for detailed member status.",
        "[etcd backup and restore](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/etcd/index#replacing-an-unhealthy-etcd-member)",
    ),
    "etcd.quorum": (
        "Quorum loss in etcd is a critical failure mode requiring manual recovery. "
        "Always maintain an odd number of etcd members (3 or 5). Never scale etcd to 2 or 4 members.",
        "[etcd quorum](https://etcd.io/docs/latest/op-guide/clustering/)",
    ),
    "network.plugin": (
        "OVNKubernetes is the recommended network plugin for OCP 4.12+. OpenShiftSDN is deprecated as of "
        "OCP 4.14 and will be removed in a future version. Migration to OVNKubernetes is required for "
        "continued support.",
        "[Network migration](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/updating_clusters/index#sdn-support-removal)",
    ),
    "registry.state": (
        "The internal image registry is required for builds and ImageStream-based deployments. "
        "If set to 'Removed', registry-dependent workloads will fail. "
        "On clusters without RWX storage, 'Managed' state requires an `emptyDir` or object-storage backend.",
        "[Image registry](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/registry/index#registry-operator-configuration-resource-overview_configuring-registry-operator)",
    ),
    "storage.default_sc": (
        "A default StorageClass is required for dynamic PVC provisioning. Without one, PVCs without an "
        "explicit storageClassName will remain in Pending state. Only one StorageClass should be marked "
        "as default.",
        "[Storage configuration](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/storage/index#storage-class-annotations_dynamic-provisioning)",
    ),
    "storage.pvcs": (
        "Unbound PVCs indicate that the requested storage could not be provisioned — often due to "
        "missing StorageClass, insufficient capacity, or access mode mismatch. "
        "Run `oc describe pvc <name>` to investigate.",
        "[Understanding persistent storage](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/storage/index#storage-persistent-storage-pvc_understanding-persistent-storage)",
    ),
    "dns.operator": (
        "The DNS Operator manages CoreDNS and is critical for service discovery. "
        "A degraded DNS Operator causes intermittent name resolution failures across the cluster. "
        "Check `oc logs -n openshift-dns-operator deployment/dns-operator`.",
        "[DNS Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/networking_operators/index#nw-dns-operator-status_dns-operator)",
    ),
    "crds": (
        "High CRD count (>500) can impact API server start time and list/watch performance. "
        "Audit CRDs for orphaned resources from uninstalled operators. "
        "Remove unused CRDs with `oc delete crd <name>` after ensuring no CR instances exist.",
        "[Custom Resources](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/operators/index#crd-managing-resources-from-crds)",
    ),
    "deprecated_apis": (
        "Clusters cannot upgrade past the version where the deprecated API is removed if active usage exists. "
        "Use `oc get apirequestcounts` to identify callers. Update clients before upgrading. "
        "Reference: https://kubernetes.io/docs/reference/using-api/deprecation-guide/",
        "[API deprecation](https://kubernetes.io/docs/reference/using-api/deprecation-guide/)",
    ),
    "webhooks.": (
        "Admission webhooks with high timeouts (>10s) or failurePolicy=Fail can block API operations "
        "when the webhook server is unavailable. Ensure webhook servers are highly available and "
        "set appropriate timeouts. Use failurePolicy=Ignore for non-critical webhooks.",
        "[Admission webhooks](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/architecture/index#configuring-dynamic-admission_admission-plug-ins)",
    ),
    "monitoring.config": (
        "Configure persistent Prometheus storage via the cluster-monitoring-config ConfigMap. "
        "Without PVC storage, metrics are lost on pod restart, breaking alerting and dashboards. "
        "Recommended: at least 40Gi for Prometheus and 2Gi for Alertmanager.",
        "[Configuring monitoring](https://docs.redhat.com/en/documentation/monitoring_stack_for_red_hat_openshift/latest/html-single/configuring_core_platform_monitoring/index#configuring-persistent-storage_storing-and-recording-data)",
    ),
    "alerts.critical": (
        "Critical alerts indicate conditions that require immediate attention. "
        "All critical alerts should be investigated and resolved as soon as possible. "
        "Use `oc -n openshift-monitoring exec -c prometheus prometheus-k8s-0 -- "
        "curl http://localhost:9090/api/v1/alerts` to retrieve firing alert details.",
        "[Monitoring alerts](https://docs.redhat.com/en/documentation/monitoring_stack_for_red_hat_openshift/latest/html-single/managing_alerts/index#getting-information-about-alerts-silences-and-alerting-rules_managing-alerts-as-an-administrator)",
    ),
    "alerts.warning": (
        "Warning alerts indicate conditions that may become critical if not addressed. "
        "Review all firing warning alerts and determine if they represent known-acceptable conditions "
        "or require remediation.",
        "[Alert management](https://docs.redhat.com/en/documentation/monitoring_stack_for_red_hat_openshift/latest/html-single/managing_alerts/index#getting-information-about-alerts-silences-and-alerting-rules_managing-alerts-as-an-administrator)",
    ),
    "master_taints": (
        "Control plane nodes should have the `node-role.kubernetes.io/master:NoSchedule` taint to "
        "prevent user workloads from being scheduled there. This taint is applied automatically during "
        "installation but may be missing on manually provisioned nodes.",
        "[Control plane taints](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/nodes/index#nodes-nodes-working-master-schedulable_nodes-nodes-managing)",
    ),
    "k8s_version": (
        "Mixed kubelet versions indicate that some nodes have not completed the MachineConfig update. "
        "Check MachineConfigPool status with `oc get mcp` and investigate degraded nodes.",
        "[Node updates](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/updating_clusters/index#machine-config-operator-node-updates_openshift-update-duration)",
    ),
    "pruning.pods": (
        "Accumulated completed pods consume etcd storage and slow list operations. "
        "Set `ttlSecondsAfterFinished` on Jobs or configure the OpenShift build pruner. "
        "Reference: `oc adm prune builds` and `oc adm prune deployments`.",
        "[Pruning objects](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/building_applications/index#pruning-objects)",
    ),
    "pruning.jobs": (
        "Stale completed Jobs accumulate in etcd and slow API list operations. "
        "Add `ttlSecondsAfterFinished: 3600` to Job specs for automatic cleanup after 1 hour.",
        "[Job cleanup](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/)",
    ),
    "proxy": (
        "Cluster-wide proxy configuration affects all cluster-to-internet traffic including operator "
        "updates, Telemetry, and Red Hat Insights. Ensure `noProxy` includes the cluster subnet "
        "CIDRs to prevent routing loops. Use `HTTPS_PROXY` for TLS-enabled proxies.",
        "[Configuring proxy](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/configuring_network_settings/index#nw-proxy-configure-object_config-cluster-wide-proxy)",
    ),
    "rq": (
        "Resource Quotas limit the total resource consumption per namespace. Without quotas, a single "
        "namespace can consume all cluster resources. Setting CPU and memory quotas on user namespaces "
        "is a Day-2 best practice.",
        "[Resource quotas](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/scalability_and_performance/index#creating-a-quota_using-quotas-and-limit-ranges)",
    ),
    "upgrade.history": (
        "Regular upgrade cadence is important for security patching and supportability. "
        "Red Hat recommends upgrading within 3 months of a new Z-stream release and staying within "
        "the supported lifecycle window.",
        "[Upgrade paths](https://access.redhat.com/labs/ocpupgradegraph/)",
    ),
    "apiserver.tls": (
        "The TLS security profile controls which cipher suites and TLS versions are accepted by the "
        "API server and other services. 'Modern' enforces TLS 1.3 only. 'Intermediate' (default) "
        "allows TLS 1.2+. 'Old' should never be used in production.",
        "[TLS security profiles](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/security_and_compliance/index#tls-profiles-kubernetes-configuring_tls-security-profiles)",
    ),
    "apiserver.audit": (
        "Audit logging is essential for compliance and incident investigation. "
        "'Default' logs basic access. 'WriteRequestBodies' additionally captures request bodies for "
        "write operations. 'AllRequestBodies' captures all request bodies — use with caution.",
        "[API audit logging](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/security_and_compliance/index#about-audit-log-profiles_audit-log-policy-config)",
    ),
    "limitranges": (
        "LimitRanges enforce default resource requests/limits on containers. Without them, containers "
        "can consume unlimited resources within a namespace, bypassing ResourceQuota controls.",
        "[LimitRanges](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/scalability_and_performance/index#admin-quota-limits_using-quotas-and-limit-ranges)",
    ),
    "op_approval": (
        "Manual installPlanApproval prevents unplanned operator upgrades. Review and approve install "
        "plans during scheduled maintenance windows. Use `oc get installplan -A` to see pending plans.",
        "[Managing operators](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/operators/index#olm-approving-pending-upgrade_olm-upgrading-operators)",
    ),
    "deploymentconfigs": (
        "DeploymentConfig resources are deprecated in OCP 4.14 and will be removed in a future version. "
        "Migrate to Kubernetes Deployments for long-term supportability.",
        "[Migrating from DeploymentConfigs](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/building_applications/index#deployments-and-deploymentconfigs_what-deployments-are)",
    ),
    "scc.custom": (
        "Custom SCCs may grant elevated privileges beyond what is necessary. Review each custom SCC "
        "to ensure it follows the principle of least privilege. Where possible, prefer built-in SCCs "
        "or use Pod Security Admission (PSA) policies instead.",
        "[Managing SCCs](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/authentication_and_authorization/index#managing-pod-security-policies)",
    ),
    "scc.privileged_users": (
        "The 'privileged' SCC grants unrestricted access to the host — equivalent to root on the node. "
        "Only system service accounts should require this SCC. Audit all non-system principals and "
        "revoke access where it is not strictly required.",
        "[SCC security](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/authentication_and_authorization/index#role-based-access-to-ssc_configuring-internal-oauth)",
    ),
    "oauth.idp": (
        "The default `kubeadmin` user should be removed after external identity providers are configured. "
        "OAuth supports LDAP, HTPasswd, GitHub, GitLab, OpenID Connect, and others. "
        "Use RBAC to limit cluster-admin access to a minimal set of principals.",
        "[Configuring OAuth](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/authentication_and_authorization/index#configuring-identity-providers)",
    ),
    "rbac.cluster_admin": (
        "The cluster-admin role grants full, unrestricted access to every resource in the cluster. "
        "Follow the principle of least privilege — assign cluster-admin only to personnel who "
        "require unrestricted access and audit the list regularly.",
        "[Using RBAC](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/authentication_and_authorization/index#creating-cluster-admin_using-rbac)",
    ),
    "compliance": (
        "The Compliance Operator automates security scanning against profiles such as CIS Benchmark, "
        "NIST 800-53, and STIG. It provides continuous compliance monitoring and can automatically "
        "remediate findings where supported.",
        "[Compliance Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/security_and_compliance/index#compliance-operator-understanding)",
    ),
    "csr": (
        "Pending CSRs typically indicate new nodes waiting for certificates to be approved. "
        "In manual approval mode (`oc adm certificate approve <name>`), pending CSRs will block "
        "node join. In auto-approve mode, pending CSRs may indicate a bootstrapping failure.",
        "[Approving CSRs](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/installing_on_any_platform/index#installation-approve-csrs_installing-platform-agnostic)",
    ),
    "node.alloc": (
        "CPU/memory request percentages above 90% of node allocatable capacity indicate "
        "the node is heavily scheduled. New pods requiring resources may not be schedulable. "
        "Consider adding nodes or reducing resource requests. Limits exceeding 100% indicate "
        "over-commitment — pods may be OOM-killed under pressure.",
        "[Resource management](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/nodes/index#nodes-nodes-resources-configuring)",
    ),
    "etcd.wal": (
        "etcd WAL fsync latency directly impacts write throughput and leader elections. "
        "P99 latency above 10ms indicates slow disk I/O. Above 50ms, etcd may begin "
        "losing leadership and causing cluster instability. Use NVMe/SSD storage for etcd. "
        "On baremetal, dedicate a partition for /var/lib/etcd.",
        "[etcd hardware recommendations](https://etcd.io/docs/latest/op-guide/hardware/)",
    ),
    "etcd.backend": (
        "Backend commit latency reflects boltdb write performance. High latency (>25ms P99) "
        "combined with high WAL fsync indicates an I/O bottleneck. Consider running "
        "`etcdctl defrag` during a maintenance window to reclaim space and improve performance.",
        "[etcd performance](https://etcd.io/docs/latest/op-guide/performance/)",
    ),
    "etcd.leader": (
        "Frequent leader elections indicate etcd instability — often caused by high disk "
        "latency, network timeouts, or resource contention. Each leader election causes a "
        "brief write-unavailability window. More than 3 elections/hour warrants investigation.",
        "[etcd troubleshooting](https://access.redhat.com/solutions/4885641)",
    ),
    "etcd.db": (
        "etcd's default storage quota is 8 GiB. Once reached, etcd stops accepting writes "
        "and the cluster enters read-only mode. Run periodic compaction and defrag. "
        "Monitor `etcd_mvcc_db_total_size_in_bytes` and set up an alert at 70% of quota.",
        "[etcd compaction](https://etcd.io/docs/latest/op-guide/maintenance/)",
    ),
    "etcd.proposals": (
        "Failed raft proposals indicate that some write requests could not be committed. "
        "This is often caused by a slow or failed cluster member. Investigate etcd member "
        "health and check disk/network latency on all control plane nodes.",
        "[etcd raft tuning](https://etcd.io/docs/latest/tuning/)",
    ),
    "apiserver.latency": (
        "API server P99 latency above 500ms can cause timeouts in kubelet, controller-manager, "
        "and scheduler operations, leading to slow pod scheduling and unreliable autoscaling. "
        "High latency is often caused by etcd slowness, resource exhaustion, or excessive API "
        "calls from custom operators.",
        "[API server troubleshooting](https://access.redhat.com/solutions/4465131)",
    ),
    "pvc.util": (
        "PVCs above 75% utilization may fill up unexpectedly during peak workload. "
        "Configure volume expansion (if the StorageClass allows it) or migrate workloads "
        "before the volume reaches 100%. Alert on PVCs above 80%.",
        "[Expanding PVCs](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/storage/index#expanding-pvc-filesystem_expanding-persistent-volumes)",
    ),
    "namespaces": (
        "Namespace sprawl (many unused or abandoned namespaces) increases management overhead and "
        "attack surface. Regularly audit namespaces for activity and remove those that are no longer "
        "in use. Consider namespace-level resource quotas and network policies.",
        "[Namespaces](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/building_applications/index#working-with-projects)",
    ),
    "subs.approval": (
        "Automatic installPlanApproval causes operators to upgrade automatically when new versions "
        "are available in the channel. This can introduce breaking changes without notice. "
        "Use Manual approval and review release notes before each operator upgrade.",
        "[Subscription approval](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/operators/index#olm-approving-pending-upgrade_olm-upgrading-operators)",
    ),
}


def get_note(check_id: str, ocp_version: str = "latest") -> tuple[str, str] | None:
    """Return (note, link) for a check if a note exists, else None."""
    knowledge_base = load_kb()
    kb_note = knowledge_base.get_note(check_id, ocp_version)
    if kb_note is not None:
        return kb_note
    resolved_version = resolve_version(ocp_version, knowledge_base.active_versions)
    for key, (note, link) in _CHECK_NOTES.items():
        if key in check_id:
            if "](" in link and link.endswith(")"):
                label, url = link.rsplit("](", 1)
                resolved_link = _resolve_default_doc_link(url[:-1], resolved_version)
                return note, f"{label}]({resolved_link})"
            return note, _resolve_default_doc_link(link, resolved_version)
    return None
