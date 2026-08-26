# Native evaluator rules vs OpenShift 4.22 on-disk docs

**Landed in `scoring_veracity` (2026-08-25):** engine conflicts and mixed mappings for `7.1.nodes.master_sched`, `7.1.sys.fips`, `7.3.net.featuregates`, 7.1/7.2 install-min severity split, WAL 50 ms FAIL, and 7.3 etcd metric placeholders were addressed on branch `scoring_veracity`. Plan: `cursor_plans/scoring_veracity_2026-08-25.md`. Tables below remain the **pre-change audit snapshot**; they are not rewritten here.

Corpus (canonical): `~/git_projects/openshift_documentation/Openshift_Container_Platform-4.22-docs/txt/`  
Engine source: [01_evaluator_rules.md](01_evaluator_rules.md)  
Search preference: install / etcd / operators / authentication guides. `*_apis-en-US.txt` not used. `Openshift_Container_Platform-4.22-monitoring-en-US.txt` is an 87-line stub — monitoring PVC language is **not** in this 4.22 dump.

## Classification legend

| Class | Meaning |
|-------|---------|
| aligned | 4.22 txt states the same threshold or required condition |
| mixed | part of the matrix is in docs; part is not |
| docs-silent | no matching number or required mapping in 4.22 txt |
| conflict | 4.22 txt states a different number or forbids the mapping |
| engineering-judgment | code encodes practice; docs describe the object but set no PASS/FAIL bar |

Quotes ≤ 40 words. Paths are under `Openshift_Container_Platform-4.22-docs/txt/`.

---

## Shared helpers

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.1.subs.approval` / `7.6.op_approval` | Automatic `installPlanApproval` → WARNING | `Openshift_Container_Platform-4.22-operators-en-US.txt`: Automatic or Manual are both valid UI choices | mixed | **Conflict for CNV:** `Openshift_Container_Platform-4.22-virtualization-en-US.txt` says use Automatic to avoid support risk. Engine still WARNs. |
| CPU/RAM/disk constants 4 / 2 / 16 / 8 / 100 | Used by 7.1 (WARNING) and 7.2 (FAIL for CPU/RAM) | `Openshift_Container_Platform-4.22-installing_on_any_platform-en-US.txt` Table 1.2: control plane 4 vCPU, 16 GB, 100 GB; compute 2, 8 GB, 100 GB | mixed | Numbers **aligned**. Status mapping (WARNING vs FAIL vs 7.1 worker disk INFO) is **not** in the table. Docs say GB not GiB. |

---

## 7.1

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.1.clusterversion.id` | Always INFO | none found | docs-silent | Inventory |
| `7.1.clusterversion.channel` | stable/eus PASS; fast/candidate/other WARNING | channels exist in install/update guides; no “fast = not production” FAIL/WARN matrix | engineering-judgment | |
| `7.1.clusterversion.updates` | Any availableUpdates → WARNING | none found as a defect | engineering-judgment | Being behind a channel is often expected |
| `7.1.clusterversion.history` | Completed → PASS; none N/A | none found | docs-silent | |
| `7.1.clusterversion.failing` | Failing=True → FAIL | ClusterVersion Failing is a platform condition (operators / updating guides) | aligned | Qualitative |
| `7.1.infra.platform` / `.apiurl` | INFO | none found as scored checks | docs-silent | |
| `7.1.infra.topology` | Both HighlyAvailable → PASS else WARNING | `installing_on_bare_metal-en-US.txt`: fields set to HighlyAvailable; control plane must be HighlyAvailable | aligned | |
| `7.1.infra.vips` | VIP present → PASS; absent → **no row** | IPI VIP language in install guides | mixed | Absence is not FAIL |
| `7.1.infra.installer` / `.hypervisor` / `.restricted` | SKIPPED/INFO/N/A | install-config platforms documented | docs-silent | Status is inventory, not a SLA |
| `7.1.subs` empty | N/A | none found | docs-silent | |
| `7.1.sub.{name}` | CSV Failed FAIL; pending WARNING; AtLatestKnown PASS | operators CSV phases documented | mixed | Exact state matrix is engine |
| `7.1.nodes.os` | All RHCOS/CoreOS PASS else INFO | Table 1.2 Operating System RHCOS | mixed | INFO not FAIL for RHEL workers |
| `7.1.nodes.master_cpu` / `.master_mem` / `.master_disk` | Below min WARNING | Table 1.2 | mixed | Docs do not say WARNING |
| `7.1.nodes.master_sched` | Always PASS | `installing_on_bare_metal-en-US.txt` / vsphere: set `mastersSchedulable` **false** for dedicated control plane | conflict | Engine never WARNs |
| `7.1.nodes.master_kube` | Skew WARNING | none found as 7.1-specific | engineering-judgment | |
| `7.1.nodes.worker_disk` | Below 100 INFO | Table 1.2 compute 100 GB | mixed | INFO understates the install minimum |
| `7.1.nodes.arch` | Mixed INFO | none found | docs-silent | |
| `7.1.sys.firewall` | Proxy → WARNING | proxy is a supported config | engineering-judgment | |
| `7.1.sys.proxy` | Always PASS if collected | proxy CR documented | docs-silent | |
| `7.1.sys.sdn` | OVN PASS; SDN WARNING | SDN removal/migration is product direction; 4.22 txt search did not yield a clean “OpenShiftSDN deprecated” hit in this dump | engineering-judgment | |
| `7.1.sys.machine_net` / `.shared_net` | CIDRs found PASS else INFO | install-config networking | docs-silent | |
| `7.1.sys.dns_pods` / `.dns_config` | Not Running WARNING / SKIPPED | DNS operator health | mixed | |
| `7.1.sys.swap` / `.netmgr` / `.chrony` | Always PASS | RHCOS defaults described in nodes/install; no live probe | engineering-judgment | |
| `7.1.sys.selinux` | CoreOS → PASS else INFO | SELinux on RHCOS | mixed | |
| `7.1.sys.entropy` | Always INFO | none found | docs-silent | |
| `7.1.sys.ptp` / `.hugepages` / `.gpu` | Presence PASS else N/A | optional features | docs-silent | |
| `7.1.sys.ntp` | Always N/A | chrony vs ntpd | aligned | RHCOS uses chrony |
| `7.1.sys.fips` | Always PASS | FIPS is an install-time choice, not “always healthy” | conflict | Disabled FIPS still PASS |
| `7.1.sys.auth` | No IdP or HTPasswd-only WARNING | `authentication_and_authorization-en-US.txt`: remove kubeadmin; HTPasswd is a valid IdP type | mixed | kubeadmin-only WARNING aligned in spirit; HTPasswd-only WARNING is judgment |
| `7.1.sys.scc` | Always PASS | SCC inventory | docs-silent | Contrast 7.7 custom SCC WARNING |
| `7.1.sys.remote_health` | Insights not Available WARNING | Insights optional / disconnected | engineering-judgment | |

---

## 7.2

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.2.topo.consistent_ocp` / `.consistent_os` | Skew WARNING | none found as a numeric SLA | engineering-judgment | |
| `7.2.topo.master_count` | 3 PASS, 1 INFO, else WARNING | SNO and HA topologies documented (`installing_on_a_single_node`, HA install) | mixed | Two-node OpenShift exists as its own guide; engine WARNs non-3/non-1 |
| `7.2.topo.master_az` | &lt;3 zones WARNING | none found requiring 3 zone labels | engineering-judgment | |
| `7.2.topo.haproxy_ha` | replicas and available ≥2 PASS | ingress replicas documented | mixed | Default replicas=2 is engine |
| `7.2.topo.routing_scale` / `.sdn_nodes` / `.sdn_pods` | Always PASS | none found | docs-silent | |
| `7.2.node.{short}.ready` | Not Ready FAIL; pressure WARNING | Node Ready is core Kubernetes/OCP | aligned | Pressure mapping is judgment |
| `7.2.node.{short}.os` / `.kubelet` | INFO | none found | docs-silent | |
| `7.2.node.{short}.cpu` / `.memory` | Below Table 1.2 → **FAIL** | Table 1.2 | mixed | Same numbers as 7.1; **FAIL** vs 7.1 **WARNING** |
| `7.2.node.{short}.disk` | &lt;100 WARNING | Table 1.2 100 GB | mixed | |
| `7.2.node.{short}.sysreserved` | ≥64 GiB RAM without reservation WARNING | none found for 64 GiB trigger or 1–2Gi text | engineering-judgment | |
| `7.2.mcp.{name}` | Degraded FAIL; updating/paused WARNING | MCP Degraded/Updated conditions | mixed | Paused+healthy WARNING is judgment |
| `7.2.etcd.members` / `.quorum` | Degraded FAIL; Available false / Progressing WARNING | etcd member health | mixed | Progressing named “quorum” is engine wording |
| `7.2.etcd.pod_health` | Not Running FAIL | etcd static pods | aligned | |
| `7.2.etcd.guards` | Not Running WARNING | none found as scored | engineering-judgment | |
| `7.2.nodes` / `.etcd.pods` N/A | Missing data | none found | docs-silent | |

---

## 7.3

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.3.co.{name}` | Degraded FAIL; not Available / Progressing WARNING | ClusterOperator conditions | aligned | |
| `7.3.network.plugin` | OpenShiftSDN WARNING | no clean 4.22 txt hit in this dump | engineering-judgment | |
| `7.3.network.cluster_cidr` / `.service_cidr` | INFO | documented fields | docs-silent | |
| `7.3.ingress.{name}` | Not Available FAIL; replica shortfall WARNING | IngressController Available | mixed | |
| `7.3.registry.state` | Removed WARNING | registry managementState | mixed | Removed is valid for some designs |
| `7.3.dns.operator` | Degraded FAIL | DNS operator | aligned | |
| `7.3.webhooks.*` | Fail+critical NS FAIL; timeout&gt;10 or Fail WARNING | none found for 10s or those prefixes | engineering-judgment | Comment cites k8s failurePolicy URL, not 4.22 txt |
| `7.3.monitoring.config` | No CM or no PVC-like yaml → FAIL | `monitoring-en-US.txt` stub (87 lines); **none found** | docs-silent | Engine comment cites 4.18 HTML |
| `7.3.version` | History not Completed WARNING | ClusterVersion history | mixed | |
| `7.3.etcd.endpoints` | &lt;3 members WARNING | HA etcd three members | aligned | |
| `7.3.etcd.leader` / `.health` / `3_5_*` placeholders | SKIPPED or string scrape | etcd practices exist but these rows do not score WAL/RTT | docs-silent | Real numbers live in 7.8 |
| `7.3.haproxy.status` / `.ingress.tuning` / `.sharding` | See 01 | sharding/tuning optional | engineering-judgment | |
| `7.3.storage.csi` | No CSI WARNING | CSI is default in 4.x | mixed | |
| `7.3.storage.flexvolumes` | Flex WARNING | flex deprecated | aligned | |
| `7.3.storage.default_sc` | No default WARNING | default StorageClass | mixed | |
| `7.3.storage.pvs` / `.pvcs` | Failed/Pending / unbound WARNING | phases documented | mixed | |
| `7.3.crds` | &gt;500 WARNING | none found | engineering-judgment | |
| `7.3.deprecated_apis` | removedInRelease + traffic WARNING | API removal notices | mixed | |
| `7.3.net.kubeproxy` / `.ovnkube` | OVN N/A kube-proxy; OVN PASS | OVN is default CNI | aligned | |
| `7.3.net.featuregates` | Always PASS if COs present | **does not detect** TechPreview | conflict | Evidence claims “not detected” without checking FeatureGate |
| `7.3.net.ipstack` / `.kubelet_config` | Always PASS | none found as PASS rules | docs-silent | |
| `7.3.net.ipsec` / `.multinet` / `.hwnet` | INFO/N/A | optional | docs-silent | |
| `7.3.misc.*` SKIPPED/N/A/always PASS | See 01 | none found | docs-silent | Includes always-PASS master_config and capabilities |
| `7.3.misc.cgroups` | Heuristic v2 PASS | cgroup v2 on RHCOS 9 | engineering-judgment | |
| `7.3.misc.mcp` | Degraded MCP WARNING (not FAIL) | MCP Degraded | mixed | 7.5 uses FAIL for same helper |

---

## 7.4

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.4.{product}` inventory | not found N/A; error SKIPPED; else INFO | optional operators | docs-silent | Never FAIL for “not installed” |
| `7.4.cnv.state` | Degraded FAIL | `virtualization-en-US.txt` HyperConverged health | aligned | |
| `7.4.cnv.kubevirt` | phase Deployed PASS else WARNING | KubeVirt Deployed | mixed | |
| `7.4.cnv.pods` | not Running WARNING | pod phase | mixed | |
| `7.4.cnv.live_migratable` | LiveMigratable False WARNING | live migration | mixed | evictionStrategy INFO is judgment |
| `7.4.acm.*` / `.logging.*` | Hub/agent/logging Ready | layered product docs (ACM/logging may be separate titles) | mixed | Loki INFO only |

ODF 4.22 tree was **not** required: no ODF-specific native check_id in 7.4 inventory list.

---

## 7.5

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.5.kubelet_health` | Not Ready WARNING (not FAIL) | Node Ready | mixed | 7.2 per-node Ready is FAIL |
| `7.5.mcp_health` / `.operator_state` | Degraded FAIL | CO/MCP Degraded | aligned | |
| `7.5.registry_health` | Removed INFO | managementState | mixed | 7.3 Removed is WARNING |
| `7.5.pod_restarts` | restartCount &gt;10 WARNING | none found | engineering-judgment | annotate helper does not change status |
| `7.5.node_roles` | No role labels FAIL | node-role labels required for scheduling | aligned | |
| `7.5.machineset` / `.pdb` / `.vol_mount` | SKIPPED | none found | docs-silent | |
| `7.5.alerts.cp` / `.node` / `.overcommit` | Keyword match WARNING | alertnames not specified in txt as this split | engineering-judgment | |
| `7.5.dns_health` | Available True PASS | DNS operator | mixed | |
| `7.5.alerts.critical` | severity critical FAIL | Alertmanager severity | mixed | |
| `7.5.alerts.warning` / `.info` | warning WARNING; info INFO | same | mixed | |
| `7.5.pods.failed` | Failed/Unknown WARNING | pod phases | mixed | |
| `7.5.pods.crashloop` | CrashLoopBackOff FAIL | well-known failure | aligned | |
| `7.5.node.{short}.utilization` | CPU 80/60, mem 85/70 | none found | engineering-judgment | |
| `7.5.master_taints` | Missing NoSchedule WARNING unless compact INFO | compact/three-node documented; taints for dedicated CP | mixed | |
| `7.5.k8s_version` | Mixed kubelet WARNING | none found | engineering-judgment | |
| `7.5.pruning.pods` | Succeeded&gt;200 or Failed&gt;50 WARNING | none found | engineering-judgment | |
| `7.5.pruning.jobs` | Orphan jobs &gt;100 WARNING | none found | engineering-judgment | |
| `7.5.alerts` / `.pods` / `.node_util` N/A | Missing data | none found | docs-silent | |
| `7.5.alerts.firing` | Empty list PASS | none found | docs-silent | |
| `7.5.pods.health` | No failed pods PASS | none found | docs-silent | |

---

## 7.6

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.6.cluster_quota` / `.rq` / `.limitranges` / `.req_limits` | Optional: INFO if none | quotas optional | aligned | Comments match “optional governance” |
| `7.6.node_expected` / prune SKIPPED ids | SKIPPED | none found | docs-silent | |
| `7.6.pv_usage` | Always PASS | none found | docs-silent | |
| `7.6.prune.builds` | Always PASS | none found | engineering-judgment | |
| `7.6.prune.ns` | &gt;100 namespaces WARNING | none found | engineering-judgment | |
| `7.6.namespaces` | &gt;50 **user** NS WARNING | none found | engineering-judgment | Two different sprawl bars (50 vs 100) |
| `7.6.infra_nodes` | No infra N/A | infra role optional | aligned | |
| `7.6.image_mgmt` | INFO | image.config | docs-silent | |
| `7.6.csr_pending` | Pending WARNING | CSRs | mixed | |
| `7.6.custom_certs` / `.mcp_max_unavailable` | Always PASS | none found | docs-silent | |
| `7.6.node_ssh` | SKIPPED | none found | docs-silent | |
| `7.6.proxy` | Configured INFO else PASS | proxy supported | docs-silent | Opposite 7.1 firewall WARNING |
| `7.6.upgrade.history` | Completed PASS | none found | docs-silent | |
| `7.6.apiserver.tls` | Old WARNING | TLS profiles Old/Intermediate/Modern | mixed | |
| `7.6.apiserver.audit` | None WARNING | audit profiles | mixed | Docs recommend not disabling; aligned in spirit |
| `7.6.deploymentconfigs` | Any DC WARNING | DC deprecated 4.14+ | aligned | |
| `7.6.storage.*` | Same as 7.3 storage | same | mixed | Duplicate scoring |
| `7.6.update_impact` / `.alert_receivers` / `.remote_health` | SKIPPED | none found | docs-silent | |

---

## 7.7

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.7.container_security` / `.psa` | Always PASS | SCC/PSA exist | docs-silent | |
| `7.7.auditing` | None WARNING; missing data PASS | same as 7.6 audit | mixed | Missing APIServer → PASS not SKIPPED |
| `7.7.encryption` | aescbc/aesgcm PASS else INFO | etcd encryption optional | mixed | Unencrypted is INFO not WARNING |
| `7.7.vuln_scan` | Compliance installed PASS else N/A | optional operator | docs-silent | |
| `7.7.tls_profile` | Always INFO | TLS profiles | docs-silent | 7.6 scores Old as WARNING |
| `7.7.file_integrity` | N/A | optional | docs-silent | |
| `7.7.scc.custom` | Custom SCC WARNING | custom SCCs are supported | engineering-judgment | |
| `7.7.scc.privileged_users` | Non-system privileged WARNING | least privilege | engineering-judgment | |
| `7.7.oauth.idp` | No IdP WARNING | kubeadmin guidance | mixed | No HTPasswd-only WARNING (unlike 7.1) |
| `7.7.rbac.cluster_admin` | &gt;5 non-system WARNING | none found for “5” | engineering-judgment | |
| `7.7.compliance` | Incomplete scan WARNING | Compliance Operator | mixed | |
| `7.7.csr` | Denied FAIL; pending WARNING | CSRs | mixed | |

---

## 7.8

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.8.node.{short}.alloc` | CPU/mem req &gt;90 or WSS &gt;85 WARNING | none found | engineering-judgment | |
| `7.8.etcd.wal.{pod}` | &gt;50 FAIL, &gt;10 WARNING | `etcd-en-US.txt`: write including fdatasync under **10ms**; fsync p99 **less than 10 ms** | mixed | **10 ms aligned.** **50 ms FAIL** not in this txt (docs treat 10 ms as the bar) |
| `7.8.etcd.backend.{pod}` | &gt;50 FAIL, &gt;25 WARNING | Metric `etcd_disk_backend_commit_duration_seconds_bucket` **named**; **no 25 ms or 50 ms** | docs-silent | |
| `7.8.etcd.leader_changes` | &gt;3 WARNING, &gt;0 INFO | Leader changes metric named; no 3/hour bar | engineering-judgment | |
| `7.8.etcd.db.{pod}` | &gt;8192 FAIL, &gt;4096 WARNING | Quota discussed; **no 8 GiB FAIL** in the hits reviewed | engineering-judgment | |
| `7.8.etcd.proposals` | Any failed WARNING | none found as hourly &gt;0 | engineering-judgment | |
| `7.8.apiserver.latency` | &gt;1000 FAIL, &gt;500 WARNING | none found in 4.22 txt (k8s SLO is not this corpus) | engineering-judgment | |
| `7.8.apiserver.errors` | 5xx &gt;1.0/s WARNING | none found | engineering-judgment | |
| `7.8.etcd.endpoint_health` | Unhealthy FAIL | etcd endpoint health | aligned | |
| `7.8.etcd.endpoint_status` | Member count ≠3 WARNING | 3-member HA | mixed | SNO would WARNING |
| `7.8.pvc.util.critical` / `.warning` / `.ok` | 90 / 75 | none found | engineering-judgment | |
| `7.8.node_alloc` / `.etcd.wal` / `.etcd.leader` / latency N/A | Missing metrics | none found | docs-silent | |

Peer RTT **&lt; 50 ms** is in `etcd-en-US.txt` but **native 7.8 does not score it** (7.3 placeholder SKIPPED).

---

## 7.9

| Check ID | Engine rule | 4.22 citation | Class | Notes |
|----------|-------------|---------------|-------|-------|
| `7.9.hw` / `{key}` SKIPPED | Missing debug | none found | docs-silent | |
| `7.9.hw.{short}.identity` / `.cpu` / `.memory` | INFO | none found | docs-silent | |
| `7.9.hw.{short}.disk` | Rotational WARNING | `etcd-en-US.txt`: SSD/NVMe for etcd | mixed | Engine flags **any** rotational disk on the node, not only etcd’s disk |

---

## Rollup

Counts are Doc 02 **data rows** (one per Check ID pattern in the tables above, including shared approval as 1 row covering two ids). Chapter tables: 7.1=32, 7.2=16, 7.3=24, 7.4=6, 7.5=20, 7.6=18, 7.7=12, 7.8=12, 7.9=3, shared=2. **Total rows = 145.**

Doc 01 has **204** pattern rows. Grouped Doc 02 rows collapse families (e.g. all `7.3.misc.*` SKIPPED). Every Doc 01 pattern is covered by a row that names it or a family (`7.3.misc.*`, `7.4.{product}`, `7.8.etcd.wal.{pod}`, etc.).

| Class | 7.1 | 7.2 | 7.3 | 7.4 | 7.5 | 7.6 | 7.7 | 7.8 | 7.9 | Shared | Total |
|-------|-----|-----|-----|-----|-----|-----|-----|-----|-----|--------|-------|
| aligned | 3 | 3 | 5 | 1 | 3 | 3 | 0 | 1 | 0 | 0 | 19 |
| mixed | 12 | 6 | 8 | 4 | 8 | 4 | 5 | 2 | 1 | 2 | 52 |
| docs-silent | 10 | 3 | 6 | 1 | 4 | 8 | 5 | 1 | 2 | 0 | 40 |
| conflict | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| engineering-judgment | 5 | 4 | 4 | 0 | 5 | 3 | 2 | 8 | 0 | 0 | 31 |
| **Sum** | 32 | 16 | 24 | 6 | 20 | 18 | 12 | 12 | 3 | 2 | **145** |

**Conflicts to treat as audit findings (not code fixes):** (1) `mastersSchedulable` always PASS vs install “set false”; (2) FIPS always PASS; (3) `7.3.net.featuregates` always PASS while claiming TechPreview was checked; plus mixed/conflict **Automatic approval** vs Virtualization “use Automatic.”

**Rationale doc:** if `docs/HC_CHECK_RATIONALE.md` disagrees with 01, this audit follows the evaluator.
