# Native evaluator scoring rules

Extracted from `scripts/health_check/hc_report/evaluators/` for the audit in `cursor_plans/hc_evaluator_rules_audit_2026-08-25.md`.

**How to read:** Each table maps a check ID (or ID pattern) to a status matrix. “Source” is the Python function that assigns `CheckResult.status`.

**Status glossary**

| Status | Engine meaning in these evaluators |
|--------|-------------------------------------|
| `PASS` | Condition met (or, in a few 7.1 rows, always reported as PASS — see matrix) |
| `FAIL` | Hard failure or unmet minimum (per-node topology CPU/RAM) |
| `WARNING` | Suboptimal, degraded-but-not-failed, or policy concern |
| `INFO` | Recorded without a defect judgment |
| `SKIPPED` | Required collect data absent (when the function chose SKIPPED rather than N/A) |
| `NOT_APPLICABLE` | Feature or data does not apply, or `_not_applicable()` |

**Missing data helper:** `_not_applicable()` in `_common.py` always returns `NOT_APPLICABLE` (default evidence: “Data not collected”).

---

## Shared helpers

Constants and helpers reused by chapter evaluators. Do not re-state different numbers in later sections.

| Item | Value / rule | Source |
|------|----------------|--------|
| Control-plane CPU floor | `_MASTER_MIN_CPU` = **4** cores | `_common.py` |
| Worker CPU floor | `_WORKER_MIN_CPU` = **2** cores | `_common.py` |
| Control-plane memory floor | `_MASTER_MIN_MEM_GIB` = **16.0** GiB | `_common.py` |
| Worker memory floor | `_WORKER_MIN_MEM_GIB` = **8.0** GiB | `_common.py` |
| Disk floor | `_MIN_DISK_GIB` = **100.0** GiB | `_common.py` |
| Disk URL on some results | `_MIN_DISK_DOCUMENTATION_URL` (OCP 4.18 install HTML, live URL — not used as 4.22 on-disk proof) | `_common.py` |
| Empty / error collect | `_is_missing`: empty dict, `_hc_error`, or `_hc_not_found` | `_common.py` |

### Operator approval strategy

| Check ID (callers set this) | What is evaluated | Status matrix | Source |
|-----------------------------|-------------------|---------------|--------|
| `7.1.subs.approval` and day-2 equivalent | Subscription `spec.installPlanApproval` | Any subscription with `Automatic` → **WARNING**. Otherwise **PASS** (including zero Automatic). | `_evaluate_approval_strategy` |

### Shared predicates (no status by themselves)

Callers map these lists to FAIL/WARNING.

| Helper | Returns | Source |
|--------|---------|--------|
| `find_degraded_operators` | Names of cluster operators whose `Degraded` condition is `True`. Empty if data missing. | `_shared_checks.py` |
| `check_mcp_degraded` | `(degraded_pool_names, updating_pool_names)`. Empty lists if data missing. | `_shared_checks.py` |
| `check_csr_pending` | `(pending, approved, denied)` CSR names. No conditions → pending. Empty if data missing. | `_shared_checks.py` |
| `node_roles` | Role names from `node-role.kubernetes.io/*` labels | `_shared_checks.py` |

---

## 7.1 Base Platform

Source file: `platform.py`. Dispatcher: `evaluate_base_platform`. Category collect: `03_base_platform`. If that folder is empty, `registry.py` emits `7.1.category` **SKIPPED** (“Category not collected”) — not listed below.

Missing ClusterVersion / Infrastructure / subscriptions / nodes objects use `_not_applicable` on the parent id (`7.1.clusterversion`, `7.1.infra`, `7.1.subs`, `7.1.nodes`).

### ClusterVersion — `_evaluate_cluster_version`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.1.clusterversion.id` | Cluster ID, desired/history version, channel | Always **INFO** | `_evaluate_cluster_version` |
| `7.1.clusterversion.channel` | `spec.channel` substring | Contains `stable` or `eus` → **PASS**. Contains `fast` or `candidate` → **WARNING**. Anything else → **WARNING** (unrecognised). | `_evaluate_channel` |
| `7.1.clusterversion.updates` | `status.availableUpdates` | Non-empty → **WARNING**. Empty → **PASS** (“latest for channel”) | `_evaluate_cluster_version` |
| `7.1.clusterversion.history` | History entries with `state == Completed` | Any completed → **PASS**. None → **NOT_APPLICABLE** | `_evaluate_cluster_version` |
| `7.1.clusterversion.failing` | Condition `type == Failing` and `status == True` | Any → **FAIL**. Else **PASS** | `_evaluate_cluster_version` |

### Infrastructure — `_evaluate_infrastructure`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.1.infra.platform` | Platform and infrastructure name | Always **INFO** | `_evaluate_infrastructure` |
| `7.1.infra.topology` | `controlPlaneTopology` and `infrastructureTopology` both `HighlyAvailable` | Both HA → **PASS**. Else **WARNING** | `_evaluate_infrastructure` |
| `7.1.infra.apiurl` | `apiServerURL` | Emitted only if URL non-empty; always **INFO**. If empty, **no check**. | `_evaluate_infrastructure` |
| `7.1.infra.vips` | API and/or ingress VIP from `platformStatus` | Emitted only if at least one VIP present; always **PASS**. If neither VIP, **no check**. | `_evaluate_infrastructure` |

### Installer / hypervisor / network mode — `_evaluate_infrastructure_details`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.1.infra.installer` | `install-config` YAML platform keys | No YAML → **SKIPPED**. Else **INFO** with UPI (`platform: none`) vs IPI cloud/baremetal labels | `_evaluate_infrastructure_installer` |
| `7.1.infra.hypervisor` | Infrastructure platform | `vsphere`, `ovirt`, `openstack`, `kubevirt` → **INFO**. Else **NOT_APPLICABLE** | `_evaluate_infrastructure_hypervisor` |
| `7.1.infra.restricted` | `imageContentSources` in install-config or proxy `trustedCA.name` | Always **INFO** (restricted vs connected wording) | `_evaluate_infrastructure_restricted` |

### Subscriptions — `_evaluate_subscriptions` / `_evaluate_single_subscription`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.1.subs` | Subscription list empty after flatten | **NOT_APPLICABLE** “No subscriptions found” | `_evaluate_subscriptions` |
| `7.1.sub.{name}` | Per-subscription state vs CSV phase | `AtLatestKnown` and CSV `Succeeded` or `Unknown` → **PASS**. Installed CSV ≠ current CSV → **WARNING**. CSV phase `Failed` → **FAIL**. State not in `AtLatestKnown` / `UpgradePending` / empty → **WARNING**. Else **PASS**. | `_evaluate_single_subscription` |
| `7.1.subs.approval` | Automatic vs Manual approval | See Shared helpers | `_evaluate_approval_strategy` |

### Node requirements (cluster-level, not per node) — `_evaluate_node_requirements`

Emitted only when node list is non-empty. Master-only checks are omitted if there are no master-role nodes. Worker disk omitted if no worker-role nodes.

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.1.nodes.os` | Node `osImage` | Every image contains `CoreOS` or `RHCOS` → **PASS**. Else **INFO** | `_evaluate_nodes_os` |
| `7.1.nodes.master_cpu` | Master capacity CPU vs `_MASTER_MIN_CPU` (4) | Any master below 4 → **WARNING**. Else **PASS** | `_evaluate_master_cpu` |
| `7.1.nodes.master_mem` | Master capacity memory vs `_MASTER_MIN_MEM_GIB` (16.0) | Any below 16 GiB → **WARNING**. Else **PASS** | `_evaluate_master_memory` |
| `7.1.nodes.master_disk` | Max sysinfo disk or ephemeral-storage vs `_MIN_DISK_GIB` (100) | Any below 100 GiB → **WARNING**. Else **PASS** | `_evaluate_master_disk` |
| `7.1.nodes.master_sched` | `scheduler.spec.mastersSchedulable` (default True if missing) | Always **PASS** (wording changes; status does not) | `_evaluate_master_schedulable` |
| `7.1.nodes.master_kube` | Unique kubelet versions on masters | Exactly one version → **PASS**. Skew → **WARNING** | `_evaluate_master_kubelet` |
| `7.1.nodes.worker_disk` | Workers vs 100 GiB (same disk signal as masters) | Any below 100 → **INFO**. Else **PASS** | `_evaluate_worker_disk` |
| `7.1.nodes.arch` | Unique `architecture` values | One arch → **PASS**. Mixed → **INFO** | `_evaluate_node_architecture` |

### System config — `_evaluate_system_config` and callees

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.1.sys.firewall` | Cluster proxy HTTP/HTTPS set | Proxy present → **WARNING**. No proxy → **PASS**. Proxy object missing → not this id (`7.1.sys.proxy` is N/A instead) | `_evaluate_system_firewall_proxy` |
| `7.1.sys.proxy` | Proxy spec | Data missing → **NOT_APPLICABLE**. Else always **PASS** (configured or not) | `_evaluate_system_firewall_proxy` |
| `7.1.sys.sdn` | Network plugin (operator relatedObjects / install-config) | Unknown → **INFO**. Name contains `OVN` → **PASS**. Else **WARNING** (SDN deprecation text if `SDN` in name) | `_evaluate_system_network` |
| `7.1.sys.machine_net` | `machineNetwork` CIDRs in install-config | Found → **PASS**. Else **INFO** | `_evaluate_system_network` |
| `7.1.sys.shared_net` | `serviceNetwork` and `clusterNetwork` cidr in install-config | Both found → **PASS**. Else **INFO** | `_evaluate_system_network` |
| `7.1.sys.dns_pods` | DNS pods from `05_components` | Data missing → **SKIPPED**. All Running → **PASS**. Else **WARNING** | `_evaluate_system_network` |
| `7.1.sys.dns_config` | DNS operator object | Present → **PASS**. Missing → **SKIPPED** | `_evaluate_system_network` |
| `7.1.sys.swap` | RHCOS default (no live swap probe) | Always **PASS** if any nodes in list | `_evaluate_system_node_baseline` |
| `7.1.sys.selinux` | Any node osImage contains `CoreOS` | Yes → **PASS**. Else **INFO** | `_evaluate_system_node_baseline` |
| `7.1.sys.netmgr` | RHCOS default NetworkManager | Always **PASS** if any nodes | `_evaluate_system_node_baseline` |
| `7.1.sys.entropy` | RHCOS entropy (no runtime probe) | Always **INFO** if any nodes | `_evaluate_system_node_baseline` |
| `7.1.sys.ptp` | Any node labels contain `ptp` (case-insensitive) | Yes → **PASS**. Else **NOT_APPLICABLE** | `_evaluate_system_node_baseline` |
| `7.1.sys.hugepages` | Capacity `hugepages-2Mi` or `hugepages-1Gi` > 0 | Any node → **PASS**. Else **NOT_APPLICABLE** | `_evaluate_system_node_resources` |
| `7.1.sys.gpu` | Capacity keys containing `gpu` or `nvidia` with value > 0 | Any node → **PASS**. Else **NOT_APPLICABLE** | `_evaluate_system_node_resources` |
| `7.1.sys.chrony` | Assumption: RHCOS uses chrony | Always **PASS** if node list non-empty | `_evaluate_system_time` |
| `7.1.sys.ntp` | Legacy ntpd | Empty node list → **NOT_APPLICABLE**. Else **NOT_APPLICABLE** (chrony message) | `_evaluate_system_time` |
| `7.1.sys.fips` | `fips: true` in install-config | Always **PASS** (wording: enabled vs not enabled) | `_evaluate_system_security` |
| `7.1.sys.auth` | OAuth identity providers | Data missing → **SKIPPED**. No IdPs → **WARNING**. All IdPs type `HTPasswd` → **WARNING**. Else **PASS** | `_evaluate_system_security` |
| `7.1.sys.scc` | SCC names vs built-in set | Data missing → **SKIPPED**. Else always **PASS** | `_evaluate_system_security` |
| `7.1.sys.remote_health` | Insights cluster operator `Available == True` | Yes → **PASS**. Else **WARNING** | `_evaluate_system_remote_health` |

Baseline/time/resource checks that require a node list emit **nothing** if the list is empty (except `7.1.sys.ntp` N/A on empty).

---

## 7.2 Topology

Source file: `topology.py`. Dispatcher: `evaluate_topology`. Collect: `04_topology`. Empty category → `7.2.category` **SKIPPED** in registry.

Missing nodes for aggregate → `7.2.topo` **NOT_APPLICABLE**. Empty node items after load → **no aggregate checks** (empty list). Missing MCP / etcd CR / etcd pods → parent **NOT_APPLICABLE**.

### Aggregate topology — `_evaluate_topology_aggregate`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.2.topo.consistent_ocp` | Unique kubelet versions | One version → **PASS**. Else **WARNING** | `_evaluate_topology_versions` |
| `7.2.topo.consistent_os` | Unique osImage | One image → **PASS**. Else **WARNING** | `_evaluate_topology_versions` |
| `7.2.topo.master_count` | Count of master or control-plane role nodes | 3 → **PASS**. 1 → **INFO** (SNO). Else **WARNING** | `_evaluate_topology_masters` |
| `7.2.topo.master_az` | Zone labels on masters | ≥3 distinct zones → **PASS**. Some zones but &lt;3 → **WARNING**. No zone labels → **WARNING** | `_evaluate_topology_masters` |
| `7.2.topo.haproxy_ha` | IngressController replicas vs available | Data/items missing → **SKIPPED**. `replicas >= 2` and `availableReplicas >= 2` → **PASS**. Else **WARNING**. Default `spec.replicas` if unset is **2**. | `_evaluate_topology_ingress` |
| `7.2.topo.routing_scale` | Router replica count vs worker count | Same skip as HAProxy. When data present, always **PASS** | `_evaluate_topology_ingress` |
| `7.2.topo.sdn_nodes` | Node count | Always **PASS** | `_evaluate_topology_network_scale` |
| `7.2.topo.sdn_pods` | Sum of node pod capacity | Always **PASS** | `_evaluate_topology_network_scale` |

### Per-node hardware — `_evaluate_node_hardware` / `_check_single_node`

Pattern `{short}` is the node name before the first `.`. Role prefix in descriptions is `7.2.1`. Master vs worker mins: `master` or `control-plane` in roles uses master CPU/RAM floors; otherwise worker floors. Role label string is sorted roles or `"worker"` if none.

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.2.node.{short}.ready` | Ready / MemoryPressure / DiskPressure / PIDPressure | Ready ≠ True → **FAIL**. Else MemoryPressure True → **WARNING**. Else DiskPressure True → **WARNING**. Else PIDPressure True → **WARNING**. Else **PASS** | `_check_node_conditions` |
| `7.2.node.{short}.os` | osImage and kernel | Always **INFO** | `_check_node_os` |
| `7.2.node.{short}.cpu` | Capacity CPU vs 4 (control plane) or 2 (other) | Below min → **FAIL**. Else **PASS** | `_check_node_cpu` |
| `7.2.node.{short}.memory` | Capacity memory vs 16.0 or 8.0 GiB | Below min → **FAIL**. Else **PASS** | `_check_node_memory` |
| `7.2.node.{short}.disk` | Sysinfo max disk else ephemeral-storage vs 100 GiB | Below 100 → **WARNING**. Else **PASS** | `_check_node_disk` |
| `7.2.node.{short}.kubelet` | kubelet and CRI versions | Always **INFO** | `_check_node_kubelet` |
| `7.2.node.{short}.sysreserved` | systemReserved on nodes with **≥ 64.0 GiB** RAM | **No check** if RAM &lt; 64 GiB, or node status config already has `systemReserved`, or a matching/global KubeletConfig already sets it. Else **WARNING**. | `_check_system_reserved` |

Missing nodes object → `7.2.nodes` **NOT_APPLICABLE**.

### MachineConfigPool — `_evaluate_mcp`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.2.mcp.{name}` | Degraded / Updating / paused / updated counts | `Degraded` True or `degradedMachineCount > 0` → **FAIL**. Updating → **WARNING**. `spec.paused == true` and counts all current → **WARNING**. Not `Updated` with `total > 0` → **WARNING**. Else **PASS** | `_evaluate_mcp` |

### Etcd operator CR — `_evaluate_etcd`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.2.etcd.members` | `EtcdMembersDegraded` / `EtcdMembersAvailable` | Degraded True → **FAIL**. Available False → **WARNING**. Else **PASS** | `_evaluate_etcd` |
| `7.2.etcd.quorum` | `EtcdMembersProgressing` True | True → **WARNING**. Else **PASS** | `_evaluate_etcd` |

### Etcd pods — `_evaluate_etcd_pods`

Pods named with `etcd-` excluding `guard`; guards are `etcd-guard`.

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.2.etcd.pods` | No etcd member pods | **NOT_APPLICABLE** | `_evaluate_etcd_pods` |
| `7.2.etcd.pod_health` | Member pod phase | Any not Running → **FAIL**. Else **PASS** | `_check_etcd_pod_health` |
| `7.2.etcd.guards` | Guard pods (omitted if none) | All Running → **PASS**. Else **WARNING** | `_check_etcd_guard_pods` |

---

## 7.3 Component Checks

Dispatcher: `evaluate_components`. Collect: `05_components`. Empty category → `7.3.category` **SKIPPED**.

### `components.py`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.3.co` | Cluster operators object missing | **NOT_APPLICABLE** | `_evaluate_cluster_operators` |
| `7.3.co.{name}` | Per cluster operator Available / Degraded / Progressing | Degraded True → **FAIL**. Available ≠ True → **WARNING**. Progressing True → **WARNING**. Else **PASS** | `_evaluate_cluster_operators` |
| `7.3.network` | Network CR missing | **NOT_APPLICABLE** | `_evaluate_network` |
| `7.3.network.plugin` | `networkType` | `OVNKubernetes` → **PASS**. `OpenShiftSDN` → **WARNING**. Other → **PASS** | `_evaluate_network` |
| `7.3.network.cluster_cidr` | Cluster CIDRs present | Emitted only if list non-empty; always **INFO** | `_evaluate_network` |
| `7.3.network.service_cidr` | Service CIDRs present | Emitted only if list non-empty; always **INFO** | `_evaluate_network` |
| `7.3.ingress` | IngressController missing | **NOT_APPLICABLE** | `_evaluate_ingress` |
| `7.3.ingress.{name}` | Per controller Available vs replicas | Available ≠ True → **FAIL**. `availableReplicas < desired` → **WARNING**. Else **PASS**. Desired defaults from spec or status or **1** | `_evaluate_ingress` |
| `7.3.registry.state` | Image registry | Missing → N/A. `managementState == Removed` → **WARNING**. Available True → **PASS**. Else **WARNING** | `_evaluate_image_registry` |
| `7.3.dns.operator` | DNS operator conditions | Missing → N/A. Degraded True → **FAIL**. Available True → **PASS**. Else **WARNING** | `_evaluate_dns` |
| `7.3.dns.config` | Cluster domain string | Emitted only if config present and domain non-empty; always **INFO** | `_evaluate_dns` |
| `7.3.webhooks.validatingwebhooks` / `.mutatingwebhooks` | Timeout and failurePolicy | Data missing → N/A. Fail policy **and** namespaceSelector values start with `openshift-` / `kube-system` / `kube-public` / `default` → **FAIL**. Else timeout > **10** or `failurePolicy == Fail` → **WARNING**. Else **PASS**. Default timeout **10**, default failurePolicy **Ignore** | `_evaluate_webhooks` |
| `7.3.monitoring.config` | `cluster-monitoring-config` | Missing CM → **FAIL**. `config.yaml` contains `volumeClaimTemplate` or `storage` → **PASS**. Else **FAIL** | `_evaluate_monitoring_config` |

### `components_infra.py`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.3.version` | ClusterVersion history[0].state | Missing CV → N/A. `Completed` → **PASS**. Else **WARNING** | `_evaluate_cluster_version` |
| `7.3.etcd.endpoints` | Lines with `etcd-`, `Running`, not `guard` | ≥3 → **PASS**. >0 and <3 → **WARNING**. Output but 0 members → **SKIPPED**. Empty output → N/A | `_evaluate_etcd_endpoints` |
| `7.3.etcd.leader` | `04_topology` etcd_status output contains `leader` | Yes → **PASS**. Else **SKIPPED** | `_evaluate_etcd_leader` |
| `7.3.etcd.health` | Same output; exit_code | exit ≠ 0 or empty → **SKIPPED**. etcd- line without Running → **FAIL**. Else **PASS** | `_evaluate_etcd_health` |
| `7.3.etcd.3_5_4` … `7.3.etcd.3_5_9` (ids with dots→underscores: `3_5_4` through `3_5_9`, plus `3_5_8_1`/`_2`/`_3`) | Prometheus placeholders | Always **SKIPPED** | `_evaluate_etcd_metrics_placeholders` |
| `7.3.ingress.agg` | Ingress missing | **NOT_APPLICABLE** | `_evaluate_ingress_aggregate` |
| `7.3.haproxy.status` | Available True count vs items | All Available → **PASS**. Else **WARNING** | `_evaluate_ingress_status` |
| `7.3.ingress.tuning` | `tuningOptions` non-empty/non-`0s` | Always **INFO** | `_evaluate_ingress_tuning` |
| `7.3.ingress.sharding` | Multiple controllers vs selectors | >1 controller and none sharded → **WARNING**. >1 and some selectors → **PASS**. Single controller → **INFO** | `_evaluate_ingress_sharding` |
| `7.3.storage.csi` | Provisioner names | Any CSI-like → **PASS**. Else **WARNING**. SC missing → N/A | `_evaluate_storage_aggregate` |
| `7.3.storage.flexvolumes` | `flex` in provisioner | Present → **WARNING**. Else **NOT_APPLICABLE** | `_evaluate_storage_aggregate` |
| `7.3.storage.default_sc` | Annotation `storageclass.kubernetes.io/is-default-class=true` | None → **WARNING**. Else **PASS** | `_evaluate_storage_classes` |
| `7.3.storage.pvs` | PV phase Failed+Pending | Any → **WARNING**. Else **PASS** | `_evaluate_pvs` |
| `7.3.storage.pvcs` | PVC phase ≠ Bound | Any → **WARNING**. Else **PASS** | `_evaluate_pvcs` |
| `7.3.crds` | CRD count | **> 500** → **WARNING**. Else **INFO** | `_evaluate_crds` |
| `7.3.deprecated_apis` | APIRequestCount `removedInRelease` and request count > 0 | Any → **WARNING**. Else **PASS** | `_evaluate_deprecated_apis` |

### `components_network.py`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.3.net.kubeproxy` | Network type | Empty type → N/A. OVNKubernetes → **NOT_APPLICABLE**. Else **INFO** | `_evaluate_net_plugin_type` |
| `7.3.net.ovnkube` | Network type | OVNKubernetes → **PASS**. Else **NOT_APPLICABLE** | `_evaluate_net_plugin_type` |
| `7.3.net.featuregates` | Cluster operators present | Missing → **SKIPPED**. Else always **PASS** (does not actually detect TechPreview) | `_evaluate_net_config` |
| `7.3.net.kubelet_config` | MachineConfig names containing `kubelet` | MCP missing → N/A. Else always **PASS** | `_evaluate_net_config` |
| `7.3.net.ipstack` | OVN ipv4/ipv6 or CIDR characters | Always **PASS** when data exists; N/A if both missing | `_evaluate_net_ip_stack` |
| `7.3.net.ipsec` | `ipsecConfig.mode` (default Disabled) | Missing operator → N/A. Else **INFO** | `_evaluate_net_ipsec` |
| `7.3.net.multinet` | NetworkAttachmentDefinitions | Always **INFO** (including “not collected”) | `_evaluate_net_additional` |
| `7.3.net.hwnet` | NNCP items | Items → **INFO**. None or not collected → **NOT_APPLICABLE** | `_evaluate_net_additional` |

### `components_misc.py`

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.3.misc.master_config` | Scheduler profile / mastersSchedulable | Missing → **SKIPPED**. Else always **PASS** | `_evaluate_misc_master_and_limits` |
| `7.3.misc.ocp_limits` | Subscription limits | Always **SKIPPED** | `_evaluate_misc_master_and_limits` |
| `7.3.misc.lb` | Infrastructure platform | Missing → N/A. Else **INFO** | `_evaluate_misc_loadbalancer` |
| `7.3.misc.metallb_installed` | Cluster operator name contains `metallb` | Installed → **PASS**. Else **NOT_APPLICABLE** | `_evaluate_misc_loadbalancer` |
| `7.3.misc.metallb_config` / `.metallb_l2` | MetalLB details | Installed → **SKIPPED**. Else **NOT_APPLICABLE** | `_evaluate_misc_loadbalancer` |
| `7.3.misc.mcp` | `check_mcp_degraded` on MachineConfigs | Missing → N/A. Degraded or updating → **WARNING**. Else **PASS** | `_evaluate_misc_mcp_and_sctp` |
| `7.3.misc.sctp` | SCTP | Always **NOT_APPLICABLE** | `_evaluate_misc_mcp_and_sctp` |
| `7.3.misc.capabilities` | ClusterVersion capabilities | Missing CV → N/A. Else always **PASS** | `_evaluate_misc_capabilities_and_workloads` |
| `7.3.misc.sandboxed` | Kata | Always **NOT_APPLICABLE** | `_evaluate_misc_capabilities_and_workloads` |
| `7.3.misc.cgroups` | Heuristic crun / RHEL 9 / CoreOS → v2 | All v2 → **PASS**. Else **INFO** | `_evaluate_misc_capabilities_and_workloads` |
| `7.3.misc.deploymentconfig` | DC query | Always **SKIPPED** | `_evaluate_misc_capabilities_and_workloads` |
| `7.3.misc.wp_enabled` | MachineConfig name contains `performance` | Detected → **PASS**. Else **INFO** | `_evaluate_misc_capabilities_and_workloads` |
| `7.3.misc.pp_mcp` / `.pp_status` / `.pp_config` | Performance profile details | Not detected → **NOT_APPLICABLE**. Detected → **SKIPPED** | `_evaluate_misc_capabilities_and_workloads` |

---

## 7.4 Layered Products

Source: `layered.py`. Dispatcher: `evaluate_layered`.

Product inventory (`_LAYERED_PRODUCTS` keys become `7.4.{product name}`): `_hc_not_found` → **NOT_APPLICABLE**; `_hc_error` → **SKIPPED**; else **INFO** “Installed.”

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.4.{product}` | Presence of listed CRs (CNV, ACM, ACS, logging, pipelines, mesh, MTV, OADP, serverless serving/eventing, Quay, Data Science) | See above | `_evaluate_layered_product` |
| `7.4.cnv.state` | HyperConverged | Not installed → N/A. Degraded True → **FAIL**. Available True → **PASS**. Else **WARNING** | `_evaluate_cnv_aggregate` |
| `7.4.cnv.kubevirt` | KubeVirt phase | Missing → **SKIPPED**. `Deployed` → **PASS**. Else **WARNING** | `_evaluate_cnv_aggregate` |
| `7.4.cnv.pods` | CNV pod phase not Running/Succeeded | Any → **WARNING**. Else **PASS**. Omitted if pod data missing | `_evaluate_cnv_aggregate` |
| `7.4.cnv.live_migratable` | VMI LiveMigratable False; VM evictionStrategy | VMI missing → **SKIPPED**. Any False → **WARNING**. Else eviction lines → **INFO**. Else **PASS** | `_evaluate_cnv_live_migratable` |
| `7.4.acm.agent` | klusterlet pods when hub missing | Found → **PASS** (then return) | `_evaluate_acm_aggregate` |
| `7.4.acm.state` | MultiClusterHub | Not installed → N/A. Phase Running or Available → **PASS**. Else **WARNING** | `_evaluate_acm_aggregate` |
| `7.4.logging.state` | ClusterLogging Ready | Not installed → N/A. Ready True → **PASS**. Else **WARNING** | `_evaluate_logging_aggregate` |
| `7.4.logging.loki` | LokiStack not `_hc_not_found` | **INFO** if present | `_evaluate_logging_aggregate` |

---

## 7.5 Cluster Health

Source: `health.py`. Dispatcher: `evaluate_cluster_health`.

**Post-pass:** `annotate_pod_restart_collection_gap` (from `evaluators/__init__.py` after parity) does **not** change status. If both `7.5.pod_restarts` and catalog id `7.5.tsr.5_5_pod_frequent_restarts` exist, it may append evidence about TSR pod keys missing from `pods_all`.

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.5.kubelet_health` | Node Ready | Missing → **SKIPPED**. Any not Ready → **WARNING**. Else **PASS** | `_evaluate_health_kubelet` |
| `7.5.mcp_health` | Degraded MCP names | Missing → **SKIPPED**. Any degraded → **FAIL**. Else **PASS** | `_evaluate_health_machine_config` |
| `7.5.operator_state` | Degraded cluster operators | Missing → **SKIPPED**. Any → **FAIL**. Else **PASS** | `_evaluate_health_operator_state` |
| `7.5.registry_health` | `managementState` | Missing → **SKIPPED**. Managed → **PASS**. Unmanaged/Removed → **INFO**. Else **WARNING** | `_evaluate_health_registry` |
| `7.5.pod_restarts` | Any container `restartCount > 10` | Missing pods → **SKIPPED**. Any → **WARNING**. Else **PASS** | `_evaluate_health_pod_restarts` |
| `7.5.node_roles` | Nodes with no role labels | Missing → **SKIPPED**. Any unlabeled → **FAIL**. Else **PASS** | `_evaluate_health_node_roles` |
| `7.5.machineset` / `.pdb` / `.vol_mount` | Not in standard collect | Always **SKIPPED** | `_evaluate_health_static_checks` |
| `7.5.alerts.cp` / `.node` / `.overcommit` | Alertname keyword buckets | Alerts missing → **SKIPPED**. Any match → **WARNING**. Else **PASS** | `_evaluate_health_alert_breakdown` |
| `7.5.dns_health` | DNS operator Available True | Missing → **SKIPPED**. True → **PASS**. Else **WARNING** | `_evaluate_health_dns` |
| `7.5.alerts` | Firing alerts object missing | **NOT_APPLICABLE** | `_evaluate_firing_alerts` |
| `7.5.alerts.firing` | Empty alert list | **PASS** (only if list empty; otherwise this id is not used) | `_evaluate_firing_alerts` |
| `7.5.alerts.critical` | severity critical | Any → **FAIL**. Else **PASS** | `_evaluate_firing_alerts` |
| `7.5.alerts.warning` | severity warning | Any → **WARNING**. Else **PASS** | `_evaluate_firing_alerts` |
| `7.5.alerts.info` | severity info | Emitted only if any; **INFO** | `_evaluate_firing_alerts` |
| `7.5.pods` | pods_all missing | **NOT_APPLICABLE** | `_evaluate_pod_health` |
| `7.5.pods.failed` | Phase Failed/Unknown | Any → **WARNING** (id used instead of `.pods.health`) | `_evaluate_pod_health` |
| `7.5.pods.health` | No Failed/Unknown | **PASS** | `_evaluate_pod_health` |
| `7.5.pods.crashloop` | Waiting reason CrashLoopBackOff | Any → **FAIL**. Else **PASS** | `_evaluate_pod_health` |
| `7.5.node.{short}.utilization` | `oc adm top nodes` CPU% / mem% | CPU>**80** or mem>**85** → **WARNING**. CPU>**60** or mem>**70** → **INFO**. Else **PASS**. Unparseable → parent N/A | `_parse_top_node_line` |
| `7.5.master_taints` | Control-plane NoSchedule taint with key containing `master` | All have taint → **PASS**. Compact (every node master+worker) missing taint → **INFO**. Else **WARNING** | `_evaluate_master_taints` |
| `7.5.k8s_version` | Unique kubelet versions | >1 → **WARNING**. Else **PASS** | `_evaluate_k8s_version` |
| `7.5.pruning.pods` | Succeeded > **200** or Failed > **50** | True → **WARNING**. Else **PASS**. Omitted if pods missing | `_evaluate_pruning` |
| `7.5.pruning.jobs` | Orphan completed jobs > **100** | True → **WARNING**. Else **PASS**. Omitted if jobs missing | `_evaluate_pruning` |

---

## 7.6 Day-2 Operations

Source: `day2.py`. Also reuses `_evaluate_storage` (same matrices as 7.3 storage default_sc / pvs / pvcs, ids under `7.6.`).

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.6.cluster_quota` | ResourceQuota items | Items → **PASS**. Empty or missing → **NOT_APPLICABLE** | `_evaluate_day2_quota_checks` |
| `7.6.req_limits` | LimitRanges | Missing collect → **SKIPPED**. None → **INFO**. Some → **PASS** | `_evaluate_day2_quota_checks` |
| `7.6.node_expected` | Capacity planning | Always **SKIPPED** | `_evaluate_day2_capacity_checks` |
| `7.6.pv_usage` | PV phases | Missing → **SKIPPED**. Else always **PASS** | `_evaluate_day2_capacity_checks` |
| `7.6.prune.builds` | Build pruning | Always **PASS** | `_evaluate_day2_pruning` |
| `7.6.prune.netpol` / `.prune.gc` | Netpol / kubelet GC | Always **SKIPPED** | `_evaluate_day2_pruning` |
| `7.6.prune.ns` | Namespace count | **> 100** → **WARNING**. Else **PASS** (0 if namespaces missing) | `_evaluate_day2_pruning` |
| `7.6.infra_nodes` | Label `node-role.kubernetes.io/infra` | Missing nodes → **SKIPPED**. Any infra → **PASS**. Else **NOT_APPLICABLE** | `_evaluate_day2_infra_nodes` |
| `7.6.update_impact` / `.alert_receivers` / `.remote_health` | Not collected | Always **SKIPPED** | `_evaluate_day2_image_and_alert_checks` |
| `7.6.image_mgmt` | Image registry allow/block lists | Missing → **SKIPPED**. Else **INFO** | `_evaluate_day2_image_and_alert_checks` |
| `7.6.csr_pending` | Pending CSRs | Missing → **SKIPPED**. Any pending → **WARNING**. Else **PASS** | `_evaluate_day2_cert_checks` |
| `7.6.custom_certs` | Certificate resources | Always **PASS** (count or “using default”) | `_evaluate_day2_cert_checks` |
| `7.6.node_ssh` | SSH | Always **SKIPPED** | `_evaluate_day2_cert_checks` |
| `7.6.mcp_max_unavailable` | MCP `maxUnavailable` | Missing → **SKIPPED**. Else always **PASS** | `_evaluate_day2_mcp_checks` |
| `7.6.proxy` | Cluster proxy URLs | Missing → N/A. Proxy set → **INFO**. Else **PASS** | `_evaluate_proxy` |
| `7.6.rq` | ResourceQuota | Collect fail → **SKIPPED**. Zero quotas → **INFO**. Else **PASS** | `_evaluate_resource_quotas` |
| `7.6.upgrade.history` | Completed history | None → **NOT_APPLICABLE**. Else **PASS** | `_evaluate_upgrade_history` |
| `7.6.apiserver.tls` | `tlsSecurityProfile.type` | Empty → **PASS**. `Old` → **WARNING**. `Custom` → **INFO**. Else **PASS** | `_evaluate_apiserver_config` |
| `7.6.apiserver.audit` | `audit.profile` | `None` → **WARNING**. WriteRequestBodies/AllRequestBodies → **PASS**. Else **PASS** | `_evaluate_apiserver_config` |
| `7.6.namespaces` | User namespaces (not openshift-/kube- prefixes) | **> 50** user NS → **WARNING**. Else **PASS** | `_evaluate_namespaces` |
| `7.6.limitranges` | LimitRange | Collect fail → **SKIPPED**. None → **INFO**. Else **PASS** | `_evaluate_limit_ranges` |
| `7.6.op_approval` | Automatic installPlanApproval | See Shared helpers | `_evaluate_operator_approval` |
| `7.6.deploymentconfigs` | DeploymentConfig items | Missing → **NOT_APPLICABLE**. Empty items → **PASS**. Any DC → **WARNING** | `_evaluate_deploymentconfigs` |
| `7.6.storage.*` | Same as 7.3 storage helpers | Same matrices; ids prefixed `7.6` | `_evaluate_storage` |

---

## 7.7 Security and Compliance

Source: `security.py`.

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.7.container_security` | SCC list present | Missing → **SKIPPED**. Else **PASS** | `_evaluate_tsr_security_aggregate` |
| `7.7.auditing` | APIServer audit profile | Data missing → **PASS** (“default”). `None` → **WARNING**. Else **PASS** | `_evaluate_tsr_security_aggregate` |
| `7.7.encryption` | `spec.encryption.type` | `aescbc` or `aesgcm` → **PASS**. Other non-empty → **INFO**. Empty → **INFO** (identity) | `_evaluate_tsr_security_aggregate` |
| `7.7.vuln_scan` | Compliance scans object | Present → **PASS**. Else **NOT_APPLICABLE** | `_evaluate_tsr_security_aggregate` |
| `7.7.tls_profile` | TLS profile type (default Intermediate) | Always **INFO** | `_evaluate_tsr_security_aggregate` |
| `7.7.psa` | PSA labels on namespaces | Always **PASS** (even if data missing) | `_evaluate_tsr_security_aggregate` |
| `7.7.file_integrity` | FIO | Always **NOT_APPLICABLE** | `_evaluate_tsr_security_aggregate` |
| `7.7.scc.custom` | SCC names not in `_DEFAULT_SCCS` | Any custom → **WARNING**. Else **PASS** | `_evaluate_scc` |
| `7.7.scc.privileged_users` | privileged SCC users not `system:` | Any → **WARNING**. Else **PASS**. Omitted if no privileged SCC | `_evaluate_scc` |
| `7.7.oauth.idp` | Identity providers | None → **WARNING**. Else **PASS** | `_evaluate_oauth` |
| `7.7.rbac.cluster_admin` | Non-system cluster-admin subjects | **> 5** → **WARNING**. Else **PASS** | `_evaluate_rbac` |
| `7.7.compliance` | Scan/suite missing | Both missing → **NOT_APPLICABLE**. Scan phase not DONE/empty → **WARNING**. Else **PASS** | `_evaluate_compliance` |
| `7.7.csr` | Denied / pending CSRs | Denied → **FAIL**. Pending → **WARNING**. Else **PASS** | `_evaluate_csr` |

---

## 7.8 Performance Metrics

Source: `metrics.py`. Missing Prometheus vectors typically **NOT_APPLICABLE**. Backend commit / DB size / proposals emit **nothing** if the vector is empty (no N/A row).

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.8.node_alloc` | No node maps | **NOT_APPLICABLE** | `_evaluate_prometheus_node_metrics` |
| `7.8.node.{short}.alloc` | CPU req%, mem req%, mem WSS% | CPU req > **90** or mem req > **90** or WSS > **85** → **WARNING**. Else **PASS**. Limits are informational only | `_build_node_alloc_check` |
| `7.8.etcd.wal` | No WAL vector | **NOT_APPLICABLE** | `_evaluate_etcd_wal_fsync` |
| `7.8.etcd.wal.{pod}` | WAL fsync P99 (seconds×1000) | **> 50** ms → **FAIL**. **> 10** ms → **WARNING**. Else **PASS** | `_evaluate_etcd_wal_fsync` |
| `7.8.etcd.backend.{pod}` | Backend commit P99 | **> 50** ms → **FAIL**. **> 25** ms → **WARNING**. Else **PASS** | `_evaluate_etcd_backend_commit` |
| `7.8.etcd.leader` | No leader-change vector | **NOT_APPLICABLE** | `_evaluate_etcd_leader_changes` |
| `7.8.etcd.leader_changes` | Sum of increases last hour | **> 3** → **WARNING**. **> 0** → **INFO**. **0** → **PASS** | `_evaluate_etcd_leader_changes` |
| `7.8.etcd.db.{pod}` | DB size bytes / 1024² | **> 8192** MiB → **FAIL**. **> 4096** MiB → **WARNING**. Else **PASS** | `_evaluate_etcd_db_size` |
| `7.8.etcd.proposals` | Failed proposals last hour | **> 0** → **WARNING**. **0** → **PASS**. Empty vector → no row | `_evaluate_etcd_proposals` |
| `7.8.apiserver.latency` | Max P99 among series | **> 1000** ms → **FAIL**. **> 500** ms → **WARNING**. Else **PASS**. No series → N/A | `_evaluate_apiserver_latency` |
| `7.8.apiserver.errors` | Sum 5xx rate | **> 1.0** req/s → **WARNING**. Else **PASS**. No series → no row | `_evaluate_apiserver_latency` |
| `7.8.etcd.endpoint_health` | etcdctl health JSON | Any `health` false → **FAIL**. Else **PASS**. Bad/missing → no row | `_check_etcd_endpoint_health` |
| `7.8.etcd.endpoint_status` | Member count | **≠ 3** → **WARNING**. **3** → **PASS** | `_check_etcd_endpoint_dbsize` |
| `7.8.pvc.util.critical` | Utilization **> 90%** | Any → **FAIL** | `_evaluate_pvc_utilization` |
| `7.8.pvc.util.warning` | **> 75** and ≤90 | Any → **WARNING** | `_evaluate_pvc_utilization` |
| `7.8.pvc.util.ok` | All ≤75 | **PASS** only if no critical and no warning | `_evaluate_pvc_utilization` |

Heartbeat metric is passed into `_evaluate_etcd_performance` and **ignored**.

---

## 7.9 Hardware Inventory

Source: `hardware.py`.

| Check ID | What is evaluated | Status matrix | Source |
|----------|-------------------|---------------|--------|
| `7.9.hw` | No `node_hw_*` files | **NOT_APPLICABLE** | `_evaluate_node_hardware_inventory` |
| `7.9.{key}` | Collect error on a node_hw file | **SKIPPED** | `_evaluate_node_hardware_inventory` |
| `7.9.hw.{short}.identity` / `.cpu` / `.memory` | Inventory fields | Always **INFO** | `_build_hw_checks` |
| `7.9.hw.{short}.disk` | Any disk `rotational` true | Yes → **WARNING**. Else **PASS**. Omitted if no disks | `_build_hw_checks` |

---

## Completeness

- **Extraction date:** 2026-08-25  
- **Method:** Every `CheckResult(` in `scripts/health_check/hc_report/evaluators/` except the `_not_applicable` / `_evaluate_approval_strategy` constructors already covered under Shared helpers. Loop bodies map to one pattern row (e.g. `7.3.co.{name}`).  
- **Constructor counts (not equal to row counts):** `platform.py` 61, `topology.py` 32, `components.py` 18, `components_infra.py` 28, `components_network.py` 13, `components_misc.py` 19, `layered.py` 22, `health.py` 46, `day2.py` 44, `security.py` 27, `metrics.py` 15, `hardware.py` 5, `_common.py` 3 (`_not_applicable` + two approval returns). Verified `rg -c 'CheckResult\('` 2026-08-25.  
- **Holes found during this gate:** none remaining in 7.1–7.9 after Tasks 4–8. Registry `*.category` SKIPPED is documented in 7.1/7.2 and applies to every empty collect folder.  
- **Parity / TSR catalog constructors** in `parity.py` are out of scope.
