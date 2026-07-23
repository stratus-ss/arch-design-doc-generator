# Acme Corp OCP-V — Architecture Decision Record (EXAMPLE)

> **This is a worked example for reference only.** All decisions, names, and values are fictional and representative of a typical OCP-V engagement. Use this file to understand the expected level of detail and format before filling in your own ADR. The Issue field in this example is a concise problem statement — the Issue field in `ADR_template.md` provides coaching guidance on what to consider when writing it.

---

## Installation & Provisioning

### ADR 1: On-Prem Cluster Installation Host (Bastion)

- **Issue**: Hub and spoke clusters require different provisioning methods at scale — hub clusters need a reliable single-cluster install path and spoke/edge clusters require automation capable of deploying 400+ sites without a bastion per site.
- **Decision**: ACM ZTP for all cluster tiers (DC, campus, branch). Hub clusters bootstrapped via Agent-based Installer. Spoke clusters provisioned via the Assisted Installer service running on their ACM hub using ZTP ClusterInstance CRs. No IPI; no per-site bastion required.
- **Status**: Decided (2026-01-15)
- **Assumptions**:
  - All sites are ≥3-node compact clusters; no single-node deployments
  - Cisco hardware supports virtual media mount via Redfish for ZTP discovery ISO delivery
  - AAP available to template ClusterInstance and related CRs
- **Argument**:
  - ACM ZTP provides a single unified provisioning path across all tiers, eliminating parallel toolchains
  - The Assisted Installer handles bare-metal discovery and installation without a bastion host
  - Red Hat scale lab has validated 3,500+ clusters from a single ACM hub

---

### ADR 2: On-Prem OpenShift Version

- **Issue**: Target OCP version must be chosen before installation; version selection affects support lifecycle, feature availability, and third-party operator compatibility (notably Rubrik CBT).
- **Decision**: OCP 4.21. Track latest GA for year one to access Rubrik CBT when available, then revert to N-1 policy.
- **Status**: Decided (2026-01-15)
- **Assumptions**:
  - Rubrik CBT feature reaches GA by OCP 4.22
  - No other third-party operator pins to an older release
- **Argument**:
  - 4.21 provides the broadest current feature set
  - Tracking latest GA in year one accepts a faster upgrade cadence in exchange for feature access
  - Revert to N-1 once Rubrik CBT parity is achieved to reduce churn

---

### ADR 3: Initial Cluster Network CIDRs and Pod Limits

- **Issue**: Pod subnet, service subnet, and host CIDR must be finalized before installation — they cannot be changed post-install. Pod-per-node limit must accommodate VM density plus system pods.
- **Decision**: PodSubnet `10.128.0.0/14`, ServicesSubnet `172.30.0.0/16`, host CIDR `/23`. Same non-routable ranges reused across all clusters. Pods-per-node: 500. Branch/campus sites share existing subnets where dedicated OCP subnets are unavailable.
- **Status**: Resolved (2026-01-20)
- **Assumptions**:
  - /23 provides headroom for up to 32 nodes per cluster
  - 500 pods-per-node accommodates VM density plus system workloads and sidecars
- **Argument**:
  - Reusing non-routable CIDRs simplifies fleet management — no per-cluster routing required
  - 500 pod limit chosen based on branch VM density (3–5 VMs) plus platform overhead baseline

---

### ADR 4: Pull Through Container Image Cache

- **Issue**: Public registry rate limiting and WAN dependency are unacceptable for a 400-site fleet — a pull-through cache is required to support partially disconnected branches and avoid Docker Hub throttling.
- **Decision**: Nexus Repository Manager (enterprise) as the pull-through cache and container registry for all cluster types. Accessible from DC, campus, and branch clusters via existing WAN connectivity.
- **Status**: Confirmed (2026-01-18)
- **Assumptions**:
  - Nexus will remain accessible to all cluster types for the foreseeable future
  - Branch clusters can reach Nexus over WAN during image pull operations
- **Argument**:
  - Nexus is already the enterprise artifact store; reusing it avoids introducing a new registry product
  - Centralizing pulls reduces duplicate internet egress and enables security scanning before images reach clusters

---

### ADR 5: ACM Hub Topology

- **Issue**: A single ACM hub for 400+ clusters creates an unacceptable blast radius; split hubs must be evaluated for operational isolation, team alignment, and survivability under DC loss.
- **Decision**: Three hub pairs — DC/campus production (active/passive), branch production (active/passive), and sandbox/lab. Each active/passive pair uses ACM backup/restore schedule. No global hub.
- **Status**: Decided (2026-02-03)
- **Assumptions**:
  - ACM outage does not affect running workloads — only management operations
  - ACM active/passive backup/restore is validated on ACM 2.6+
  - Dynatrace/Splunk provide unified observability independent of ACM hub availability
- **Argument**:
  - Split hubs align with team boundaries (DC platform team vs. branch network team)
  - Active/passive within each tier provides management continuity without the complexity of separate per-DC ACM instances
  - Branch clusters have sufficiently different deployment patterns (ZTP at scale) to justify a dedicated hub

---

### ADR 6: Branch Cluster Architecture

- **Issue**: ~400 branch sites need a standardized compact cluster design for Cisco UCS M8 hardware (3U, 3 nodes) with local storage, constrained bandwidth, and no centralized SAN.
- **Decision**: 3-node compact clusters with ODF on local NVMe (replica 3). Shared existing /23 subnets. Branch storage ~1.8 TB usable per site. VM CPU/RAM sizing based on RVTools export from existing VMware estate.
- **Status**: Partially decided (2026-01-23)
- **Assumptions**:
  - Hardware racked by local technicians using pre-imaged profiles
  - /23 subnets provide sufficient IP space for OCP + VMs
  - Branch VM density: 3–5 VMs per site
- **Argument**:
  - 3-node compact is the minimum viable ODF topology matching Cisco UCS M8 hardware
  - ODF provides local block and object storage without requiring a SAN at each branch
  - Replica 3 protects against single-node failure at the cost of 3x storage overhead — acceptable given low VM count

---

### ADR 7: Host Firmware, BIOS, and CPU Vulnerability Baseline

- **Issue**: Firmware and BIOS settings must meet CIS benchmark and OCP pre-installation requirements (VT-x, VT-d) before nodes are added to production; inconsistent firmware across nodes has caused installation failures in prior engagements.
- **Decision**: Cisco CVD "virtualization" BIOS profile enforced via Intersight server profile templates. Pre-flight Ansible checks validate firmware, BIOS, and UCS version consistency before installation. IPMI encryption enabled post-install via 2-step Cisco CVD process. Not required for sandbox; mandatory before Wave 1.
- **Status**: Confirmed (2026-02-10)
- **Assumptions**:
  - Intersight manages all production nodes
  - Cisco CVD "virtualization" profile is common across VMware and OCP-V workloads
  - IPMI encryption can be enabled post-install without cluster disruption
- **Argument**:
  - Standardizing on the Cisco CVD profile simplifies Intersight profile management across VMware and OCP-V
  - Pre-flight validation prevents installation failures caused by inconsistent firmware across nodes
  - Automated checks scale to 400 sites without manual verification overhead

---

## Network & Connectivity

### ADR 8: OpenShift Network Card Naming Consistency

- **Issue**: Some Broadcom NIC models reorder interface names on reboot, which breaks NMState policies and NAD definitions that reference specific interface names.
- **Decision**: PCI placement rules enforced in Intersight server profiles resolve reordering for all production nodes. Carried into all cluster profile templates as a standard setting.
- **Status**: Resolved (2026-01-18)
- **Assumptions**:
  - All production nodes are Cisco UCS M8 managed by Intersight
- **Argument**:
  - Preemptive PCI placement rules ensure interface name stability without OS-level workarounds
  - Must be included in the standard server profile template to avoid per-node remediation at scale

---

### ADR 9: OpenShift STP and BPDUs

- **Issue**: Linux Bridge sends BPDUs by default, causing BPDUguard-enabled switch ports to shut down — an unacceptable failure mode at branch scale.
- **Decision**: OVS Bridge for all VM data traffic. Linux Bridge prohibited on any interface attached to a switch port with BPDUguard. Narrow exceptions (e.g., voice VLAN tagging edge cases) documented and reviewed.
- **Status**: Decided (2026-01-18)
- **Assumptions**:
  - OVS is the default VM data VLAN attachment
  - Where Linux Bridge is retained as an exception, those interfaces are documented with equivalent controls reviewed by security
- **Argument**:
  - OVS does not send BPDUs and provides native VLAN trunk handling
  - Prevents switch port shutdowns that would affect all VMs on a node simultaneously

---

### ADR 10: NADs Limited To Namespaces or Cluster Wide?

- **Issue**: NADs must be scoped to a namespace or the default namespace — namespace-scoped NADs require duplication across namespaces as new VM owners onboard.
- **Decision**: NADs created in the default namespace (cluster-wide). Revisit if workload consolidation introduces cross-VLAN risk that requires namespace-level isolation.
- **Status**: Decided (2026-01-18)
- **Assumptions**:
  - Clusters are separated by security tier (DMZ, standard, dedicated) — cluster-level separation is the primary isolation boundary
- **Argument**:
  - Cluster-tier separation provides primary isolation; namespace-scoped NADs add complexity with minimal benefit under the ticket-based provisioning model
  - Simplifies onboarding — new VM owners do not need NADs pre-created in their namespace

---

### ADR 11: Create All Presented VLANs or Only Those In Use

- **Issue**: VLANs trunked to each node exceed those currently in active use — building NMState/NAD configs for all presented VLANs up-front avoids post-deployment changes when new workloads onboard.
- **Decision**: All known VLANs configured at build time. NMState policies and NADs created for all presented VLANs during cluster deployment.
- **Status**: Decided (2026-01-18)
- **Assumptions**:
  - Required VLANs are known per site at build time
- **Argument**:
  - Pre-configuring avoids post-deployment NMState rollouts and missing VLANs during migration waves
  - FI/Intersight model provides per-vNIC VLAN control so unused VLANs carry no runtime overhead

---

### ADR 12: OpenShift Node vNIC Layout

- **Issue**: vNIC count and role assignment must be finalized before Intersight server profile templates are created — it is difficult to change post-deployment and directly feeds NMState policies and NAD definitions. Site types (DC, campus, branch) have different hardware models and traffic profiles that may justify different vNIC counts.

#### ADR 12.1: Data Center (DC) vNIC Layout

- **Issue**: DC clusters use Fabric Interconnect-managed hardware with 100G networking and FlashSystem SAN. vNIC role assignment must be finalized before server profile templates are created.
- **Decision**: 4 vNICs per node — vNIC 0: OCP management (FI-A), vNIC 1: VM data with OVS bridges (FI-B), vNIC 2: live migration, vNIC 3: backup (Rubrik via Multus). MTU: jumbo (9000) for migration/backup/management; 1500 for VM data.
- **Status**: Confirmed (2026-02-14)
- **Assumptions**:
  - UCS FI abstracts NIC redundancy — 4 logical vNICs, FI handles failover
  - 100G shared pipe with QoS is sufficient for all four traffic classes
  - Rubrik CDM ≥9.4.3 supports Multus-based backup interface
- **Argument**:
  - Dedicated backup and live migration vNICs improve operational visibility and reduce blast radius during large backup or migration windows
  - Aligns with Rubrik production best practices for backup traffic isolation

#### ADR 12.2: Campus Site vNIC Layout

- **Issue**: Campus sites use standalone rack servers without Fabric Interconnects — the vNIC layout must reflect this hardware model while preserving DC traffic separation intent.
- **Decision**: 4 vNICs logical layout aligned to DC traffic classes, implemented on standalone rack servers with Intersight-managed profiles. Bond-based redundancy replaces FI failover.
- **Status**: Confirmed (2026-02-14)
- **Assumptions**:
  - Campus hardware is standalone rack, managed via Intersight
  - FlashSystem SAN available at campus sites
- **Argument**:
  - Keeps network role consistency across tiers while aligning to actual campus hardware
  - Simplifies runbook procedures — same vNIC role naming across DC and campus

#### ADR 12.3: Branch vNIC Layout

- **Issue**: Branch sites are 3-node compact with low VM density (3–5 VMs) and constrained bandwidth (~10–25 Gb) — dedicated live migration and backup vNICs may not be justified.
- **Decision**: 2 vNICs per node — vNIC 0: OCP management, vNIC 1: VM data. Backup traverses WAN to DC Rubrik appliances over management path. Live migration shares management link — acceptable given low VM density.
- **Status**: Decided (2026-02-14)
- **Assumptions**:
  - Non-FI hardware (Cisco UCS M8); bond-based redundancy
  - Branch backup is WAN-based to DC Rubrik appliances; dedicated local backup bandwidth not required
  - 3–5 VMs per branch — live migration events infrequent and low-bandwidth
- **Argument**:
  - Overhead of provisioning 4 vNICs across ~400 branches not justified by the traffic profile
  - WAN-based backup to DC Rubrik eliminates the need for a local dedicated backup interface

---

### ADR 13: Load Balancing Strategy

- **Issue**: OCP clusters require VIPs for the API server and ingress router — built-in keepalived/haproxy vs. an external F5 integration must be decided before installation.
- **Decision**: Built-in keepalived/haproxy for all clusters. No F5 VIP pre-provisioning. F5 GTM used for DNS-level routing only (pool members are Infoblox); F5 is not in the data path for OCP traffic.
- **Status**: Decided (2026-01-22)
- **Assumptions**:
  - F5 GTM DNS integration is available and configured to route to OCP ingress IPs
  - keepalived/haproxy is sufficient for expected ingress throughput
- **Argument**:
  - Eliminates a provisioning dependency on F5 for every new cluster
  - F5 GTM in DNS path only provides global load balancing without requiring F5 configuration per cluster

---

### ADR 14: VM IP Address Management (IPAM) Strategy

- **Issue**: Migrated VMs must retain their IP addresses — DHCP reservations are keyed to MAC addresses and any IP change breaks monitoring, ACLs, and application dependencies.
- **Decision**: Existing DHCP/DNS infrastructure unchanged. MTV preserves MAC addresses during migration. No IP changes for any migrated VM. Static IP VMs validated manually during post-migration sign-off.
- **Status**: Decided (2026-01-22)
- **Assumptions**:
  - Existing DHCP reservations cover all VMs targeted for migration
  - MAC address preservation is a hard migration acceptance criterion
- **Argument**:
  - Zero IP changes eliminates a category of post-migration application failures
  - Preserving MAC addresses allows existing DHCP reservations and ACLs to remain valid without changes

---

### ADR 15: Network Policy and Microsegmentation for VMs

- **Issue**: VMs on secondary VLAN networks are not subject to Kubernetes NetworkPolicy — existing VLAN/firewall segmentation governs VM traffic, but the boundary must be understood by both platform and security teams.
- **Decision**: VMs use secondary VLAN networks only; Kubernetes NetworkPolicy does not apply. Existing firewall segmentation is the primary control. No microsegmentation tool (e.g., Illumio) deployed for OCP-V VM traffic in the initial rollout.
- **Status**: Decided (2026-01-22)
- **Assumptions**:
  - No VMs will be placed on the OCP pod network
  - Existing VLAN and firewall controls meet security tier requirements
- **Argument**:
  - VLAN/firewall segmentation is already validated and audited — no change required for migrated workloads
  - Avoiding microsegmentation agent deployment on VM nodes reduces Day 2 complexity in the initial rollout

---

### ADR 16: VM Service Exposure Strategy

- **Issue**: Migrated VMs need to be reachable by clients after migration — introducing Kubernetes Service or Route abstractions increases migration risk for lift-and-shift workloads.
- **Decision**: Direct VLAN connectivity for all migrated VMs (MAC/IP preserved). No Kubernetes Service or Route required for VM access by default. MetalLB not deployed.
- **Status**: Decided (2026-01-22)
- **Assumptions**:
  - Client applications reach VMs by IP — no DNS CNAME or VIP changes required
  - No HTTP/HTTPS load balancing requirement for migrated VMs in the initial rollout
- **Argument**:
  - Direct VLAN reachability is the lowest-risk option for lift-and-shift — zero client-side changes
  - Eliminates MetalLB dependency and per-VM Service configuration overhead

---

### ADR 17: Cluster-wide Proxy and Egress Configuration

- **Issue**: A cluster-wide proxy creates a significant operational burden at fleet scale — noProxy exception lists must be maintained across every cluster and updated whenever new internal services are added.
- **Decision**: Firewall-only egress for DC and campus clusters. No cluster-wide proxy. Branch clusters egress via SD-WAN with local firewall policy. VM traffic on bridged VLANs bypasses OCP egress controls entirely — documented for network and security teams.
- **Status**: Decided (2026-02-05)
- **Assumptions**:
  - Firewall rules are in place for required OCP egress destinations before installation
  - SD-WAN provides acceptable WAN egress for branch clusters
- **Argument**:
  - Firewall-only egress eliminates noProxy list maintenance at fleet scale
  - Branch SD-WAN egress aligns with existing network architecture

---

## Storage & Backup/DR

### ADR 18: Object Storage for On-Prem Clusters

- **Issue**: Multiple OCP-V platform components (image registry, Loki, Thanos) require S3-compatible object storage — not all sites have local S3 available and remote storage introduces WAN dependency.
- **Decision**: NetApp StorageGRID for DC/campus object storage (registry, Loki, Thanos). Branch clusters use ODF ObjectBucketClaim for local S3 where required. Branch image registry uses StorageGRID over WAN; Loki local-only at branches.
- **Status**: Confirmed (2026-02-08)
- **Assumptions**:
  - StorageGRID is available and sized for log/metric retention across DC clusters
  - Branch WAN bandwidth is sufficient for registry pull from StorageGRID
- **Argument**:
  - StorageGRID is the existing enterprise S3 platform — no new product required
  - ODF ObjectBucketClaim provides local S3 at branches without WAN dependency for time-sensitive storage

---

### ADR 19: Backup and Disaster Recovery Strategy (Cross-Site)

- **Issue**: OCP-V has no built-in SRM equivalent — DR requires composing backup tools, storage replication, and application-level strategies across DC-to-DC and DC-to-branch topologies.
- **Decision**: Rubrik CDM via Multus dedicated backup vNIC for VM-level backup (DC and campus). Async block replication between DC sites for storage-level DR. OADP for cluster-level etcd and namespace backup. No automated cross-site failover orchestration — runbook-driven failover only.
- **Status**: Decided (2026-02-12)
- **Assumptions**:
  - Rubrik CDM ≥9.4.3 supports Multus-based per-node backup connectivity
  - Block replication RPO is acceptable for the application recovery tiers
  - OADP targets StorageGRID S3 for etcd backup storage
- **Argument**:
  - Rubrik provides familiar VM-level backup tooling aligned to existing operational model
  - OADP fills the cluster-level backup gap not covered by Rubrik
  - Runbook-driven failover is acceptable given low DR test frequency requirement

---

### ADR 20: PVC Hot-Expand and CD-ROM Hot-Plug

- **Issue**: PVC hot-expand and CD-ROM hot-plug are frequent day-2 VM operations — both must be validated on the target OCP version and CSI driver before migration waves begin.
- **Decision**: PVC hot-expand confirmed supported on OCP 4.21 with ODF CSI — enabled by default. CD-ROM/ISO hot-plug enabled via `DeclarativeHotplugVolumes` feature gate (GA in OCP 4.18+). Both validated in sandbox before Wave 1.
- **Status**: Confirmed (2026-03-01)
- **Assumptions**:
  - ODF CSI driver on OCP 4.21 supports online PVC expansion
  - Filesystem expansion inside the guest still requires manual steps after disk expansion
- **Argument**:
  - Validating both operations in sandbox before Wave 1 prevents discovering compatibility issues at scale
  - GA feature gates are preferred over Tech Preview to reduce support risk

---

## Security & Compliance

### ADR 21: Secret Management and Automation Tooling

- **Issue**: GitOps and cluster bootstrapping require secrets at deploy time — manual secret management does not scale to 400 clusters.
- **Decision**: HashiCorp Vault (enterprise) via External Secrets Operator for runtime secret injection. Sealed Secrets for GitOps bootstrap path where Vault is not yet reachable. Vault integration validated in sandbox before production rollout.
- **Status**: Decided (2026-02-15)
- **Assumptions**:
  - Vault enterprise is available and sized for the fleet
  - External Secrets Operator is compatible with target OCP version
- **Argument**:
  - Vault is the existing enterprise secret manager — avoids introducing a new product
  - External Secrets Operator provides a Kubernetes-native secret injection model compatible with GitOps

---

### ADR 22: On-Prem etcd Database Encryption

- **Issue**: etcd stores all cluster Secrets in plaintext by default — compliance requirements mandate database-level encryption, not just backup-level encryption.
- **Decision**: etcd at-rest encryption enabled (AES-CBC, type: `aescbc`) on all production clusters. Key rotation quarterly. Encryption keys stored in Vault.
- **Status**: Decided (2026-02-15)
- **Assumptions**:
  - ~1-2% etcd performance overhead is acceptable
  - Quarterly key rotation procedure is documented and tested before production rollout
- **Argument**:
  - etcd-level encryption satisfies compliance requirements that mandate database-level controls
  - Backup-level encryption alone (GPG before S3) is insufficient to meet InfoSec standards

---

### ADR 23: Kubeadmin and/or Breakglass Account

- **Issue**: When the primary LDAP identity provider is unavailable, cluster administrators must still be able to access clusters for emergency operations.
- **Decision**: `kubeadmin` disabled after initial setup on all clusters. One htpasswd breakglass account per cluster; credentials stored in Vault with per-cluster path, rotation on 90-day schedule. Access requires a Vault break-glass policy approval workflow.
- **Status**: Decided (2026-02-15)
- **Assumptions**:
  - Vault is reachable during break-glass scenarios (separate availability domain from OCP identity provider)
  - 90-day rotation is achievable with the current operations team cadence
- **Argument**:
  - Disabling kubeadmin removes a well-known credential vector
  - Vault-stored htpasswd credentials are audited, rotated, and only retrievable with an approval workflow

---

### ADR 24: Kubeconfig Storage

- **Issue**: The installation kubeconfig grants cluster-admin-equivalent access — at fleet scale, hundreds of kubeconfig files must be stored securely, rotated, and retrievable under break-glass conditions.
- **Decision**: kubeconfig files stored in Vault with per-cluster paths. Access gated via RBAC-bound Vault policy (platform-admin role only). Rotation on 90-day schedule aligned with ADR 23. Access events audited in Vault audit log.
- **Status**: Decided (2026-02-15)
- **Assumptions**:
  - Vault audit log is shipped to Splunk for long-term retention
  - kubeconfig rotation does not require cluster downtime
- **Argument**:
  - Centralizing in Vault provides audit logging, access control, and rotation tooling at fleet scale
  - Aligns kubeconfig lifecycle with breakglass account lifecycle (ADR 23) for consistent operational runbook

---

### ADR 25: TLS/SSL Certificate Strategy

- **Issue**: Default OCP self-signed certificates cause TLS warnings and do not meet enterprise compliance requirements — manual certificate management does not scale to 400 clusters.
- **Decision**: cert-manager with Acme Corp internal CA. Wildcard ingress certificate per cluster issued via sub-CA delegation. API server certificate via internal CA. cert-manager manages renewal automatically.
- **Status**: Decided (2026-02-18)
- **Assumptions**:
  - Internal CA is available and issuing certificates is a self-service workflow for the platform team
  - cert-manager is compatible with target OCP version
- **Argument**:
  - cert-manager provides automated renewal at fleet scale — no manual certificate lifecycle management
  - Wildcard per cluster is the simplest model that eliminates TLS warnings without per-route certificate overhead

---

### ADR 26: CIS Benchmark Compliance Scope

- **Issue**: Both OCP and OCP-V CIS benchmarks may apply — auto-remediation via Compliance Operator can cause node reboots and must be coordinated carefully in a VM environment.
- **Decision**: OCP CIS benchmark + OCP-V CIS benchmark both scoped. Scan-then-manually-remediate approach (no auto-remediation). Tenable scanner integrated with Compliance Operator. Remediation coordinated via maintenance windows (ADR 47).
- **Status**: Decided (2026-02-20)
- **Assumptions**:
  - Tenable has an OCP-V benchmark profile or equivalent
  - Manual remediation cadence is acceptable to InfoSec
- **Argument**:
  - Auto-remediation in a VM environment risks unexpected node reboots causing VM downtime
  - Scan-then-manually-remediate provides the same compliance evidence with a controlled change process

---

### ADR 27: Audit Logging Policy

- **Issue**: OCP audit verbosity must be tuned to meet compliance requirements without overwhelming Splunk ingestion capacity across a 400-cluster fleet.
- **Decision**: `WriteRequestBodies` audit profile on all production clusters. Audit logs forwarded to Splunk via dedicated ClusterLogForwarder pipeline. Sandbox and non-prod clusters use `Default` profile.
- **Status**: Decided (2026-02-20)
- **Assumptions**:
  - Splunk has confirmed ingestion capacity for `WriteRequestBodies` volume at fleet scale
  - Audit log retention in Splunk meets compliance framework requirements
- **Argument**:
  - `WriteRequestBodies` provides evidence of all changes — satisfies PCI and InfoSec audit requirements
  - Separating prod and non-prod profiles balances coverage with log volume

---

## RBAC, Namespaces & Access

### ADR 28: Project Naming Convention for VMs

- **Issue**: Namespace naming must balance operational simplicity against RBAC granularity — a naming model must be chosen before migration waves begin as it defines the RBAC and quota boundary. Tightly coupled with ADR 29 (RBAC model) and ADR 30 (VM placement).
- **Decision**: OS-level namespaces per cluster security tier: `linux-vms`, `windows-vms`, `appliance-vms`. One namespace per OS family per cluster. Application-level namespacing deferred until a future phase.
- **Status**: Decided (2026-03-01)
- **Assumptions**:
  - Security tier separation remains at cluster level — one cluster per tier (DMZ, standard, dedicated)
- **Argument**:
  - OS-level namespaces mirror VMware cluster organization and are familiar to the operations team
  - Minimizing namespace count reduces quota and RBAC management overhead in the initial rollout

---

### ADR 29: OpenShift RBAC Assignments

- **Issue**: Multiple teams (platform admins, Linux/Windows OS teams, backup operators, app owners, read-only observers) require different access levels — roles must be defined before migration waves begin.
- **Decision**: LDAP group sync via OpenShift LDAP identity provider. Custom ClusterRoles: `vm-operator` (create/delete/restart VMs in assigned namespace), `vm-console` (VNC/serial access), `backup-operator` (read PVCs, trigger snapshots). Iterative approach: deploy minimal roles, audit denied actions, refine over 90-day period.
- **Status**: Decided (2026-03-01)
- **Assumptions**:
  - LDAP groups are structured to match OCP role boundaries
  - Privileged access management (PAM) connector integration deferred to Phase 2
- **Argument**:
  - Iterative role definition avoids over-provisioning and surfaces least-privilege gaps through actual API usage
  - Custom ClusterRoles for backup and console access cover use cases not met by built-in roles

---

### ADR 30: Location in OpenShift for Migrated VMs

- **Issue**: VMs must be assigned to namespaces aligned with operational teams and security tiers — this must be finalized before Wave 1 as it determines RBAC, quota scope, and network attachment visibility. Dependent on ADR 28 (naming convention) and ADR 29 (RBAC model).
- **Decision**: VMs placed in namespace matching OS type (`linux-vms` / `windows-vms` / `appliance-vms`) within the cluster matching their security tier. No cross-tier namespaces. Namespace assigned during migration wave planning.
- **Status**: Decided (2026-03-01)
- **Assumptions**:
  - Security tier (DMZ / standard / dedicated) is determined for every VM during triage (ADR 57)
  - One cluster per security tier — cluster boundary is the primary security control
- **Argument**:
  - Placing VMs in consistent, predictable namespaces simplifies RBAC application and operational runbooks
  - Cluster-per-tier model ensures that a misconfigured NAD in one namespace cannot expose traffic across security tiers

---

### ADR 31: Self Provisioner Disabled?

- **Issue**: Default OCP allows any authenticated user to create namespaces — in a VM-centric environment this bypasses the controlled provisioning model and creates namespace sprawl.
- **Decision**: Self-provisioner ClusterRoleBinding removed from `system:authenticated:oauth`. Namespace creation requires a ServiceNow request, which triggers a GitOps pipeline to apply the namespace manifest.
- **Status**: Decided (2026-03-01)
- **Assumptions**:
  - GitOps pipeline can provision namespaces within the ServiceNow SLA
  - All teams accept the ticket-based namespace provisioning model
- **Argument**:
  - Controlled namespace creation ensures consistent RBAC, quota, and NAD application
  - Mirrors the VMware cluster provisioning model already familiar to the operations team

---

### ADR 32: Resource Quotas and Limit Ranges for VM Namespaces

- **Issue**: Kubernetes ResourceQuota can cause unexpected VM scheduling failures in OCP-V due to auto-set memory limits (2x) and CPU limits (1 per vCPU) — quota overhead must be weighed against the operational benefit.
- **Decision**: No quotas applied to VM namespaces in the initial rollout. Revisit when multi-tenant workloads or chargeback requirements are introduced.
- **Status**: Decided (2026-03-01)
- **Assumptions**:
  - Cluster-level capacity planning (ADR 40) provides utilization governance without per-namespace quotas
  - Chargeback requirements are not in scope for Phase 1
- **Argument**:
  - Quotas with OCP-V auto-set limits cause unpredictable scheduling failures that are difficult to diagnose for VM operators unfamiliar with Kubernetes concepts
  - Capacity planning at the cluster level is sufficient for the initial rollout

---

### ADR 33: VM Console and Remote Access Strategy

- **Issue**: OCP-V provides VNC, virtctl SSH, and serial console in addition to direct SSH/RDP over VLAN — broad console access increases attack surface and must be constrained by RBAC.
- **Decision**: VNC/serial console access limited to `platform-admin` and `vm-operator` ClusterRoles. All other users access VMs via SSH/RDP over their existing VLAN path (identical to VMware today). No session recording in the initial rollout.
- **Status**: Decided (2026-03-05)
- **Assumptions**:
  - RBAC on `subresources.kubevirt.io` is sufficient to control console access
  - SSH/RDP over VLAN is available and functional for all migrated VMs post-migration
- **Argument**:
  - Limiting console access to platform and VM operators reduces the attack surface without changing the access model for app teams
  - Mirrors existing VMware console access policy (restricted to infrastructure team)

---

## VM Configuration & Scheduling

### ADR 34: On-Prem Control Plane Node Placement

- **Issue**: etcd quorum requires a majority of control plane nodes to be healthy simultaneously — physical placement across failure domains must be defined before hardware racking begins.
- **Decision**: Control plane nodes distributed across separate racks and independent power circuits at DC and campus sites. Branch sites accept single-rack placement risk (3-node compact, cross-rack not possible) — risk documented and accepted by leadership.
- **Status**: Decided (2026-02-20)
- **Assumptions**:
  - DC and campus sites have ≥2 racks available for control plane distribution
  - Branch single-rack risk is within leadership's accepted risk threshold
- **Argument**:
  - Rack-spread at DC/campus eliminates a single rack failure as a quorum-loss scenario
  - Branch single-rack risk is acknowledged — 3-node compact is the hardware constraint at those sites

---

### ADR 35: Control Plane To Host Infrastructure Load

- **Issue**: OCP-V supports schedulable masters — the boundary between control plane, platform service, and VM workloads must be defined to prevent noisy-neighbor impact on etcd.
- **Decision**: Schedulable masters with taint-based workload separation. Platform services (ingress, monitoring, logging) tolerate an `infra` taint applied to dedicated worker nodes. VM workloads excluded from master nodes via node selector and taint. 3-node branch clusters run control plane only — no VM scheduling on masters at branches.
- **Status**: Decided (2026-02-20)
- **Assumptions**:
  - DC/campus clusters have sufficient worker nodes for both platform services and VM workloads
  - Branch clusters are control-plane-only — VM scheduling uses workers (all 3 nodes are workers + masters in compact mode)
- **Argument**:
  - Taint-based separation protects etcd from resource-intensive VM workloads on the same node
  - Explicit node selector on VM workloads prevents accidental scheduling on control plane nodes

---

### ADR 36: VM Hot-Plug Configuration

- **Issue**: Hot-plug CPU and memory ratios must be validated as sufficient before production migration — changing them later requires a VM restart for each affected VM.
- **Decision**: Default hot-plug ratios accepted: 4x CPU sockets, 2x memory. Validated sufficient for current workload profile based on RVTools sizing data. Validated in sandbox on OCP 4.21.
- **Status**: Confirmed (2026-03-01)
- **Assumptions**:
  - No workloads require hot-plug ratios beyond 4x CPU sockets or 2x memory
  - Sandbox validation covers representative VM sizes from the target migration estate
- **Argument**:
  - Default ratios cover the workload profile without requiring custom HCO configuration
  - Sandbox validation before Wave 1 prevents discovering ratio insufficiency at scale

---

### ADR 37: VM Instance Types and Sizing Standards

- **Issue**: VM sizing sprawl from the VMware estate must be addressed — but introducing a strict instance type catalog before migration adds a change process layer that could delay Wave 1.
- **Decision**: Advisory-only instance types in Phase 1. Six standard sizes defined (small/medium/large × Linux/Windows). No admission control enforcement. Enforcement re-evaluated after 6 months of production data.
- **Status**: Decided (2026-03-01)
- **Assumptions**:
  - Existing provisioning workflow handles sizing requests via ServiceNow
  - Phase 1 migration uses RVTools sizing as-is without enforced normalization
- **Argument**:
  - Advisory instance types allow the team to collect real sizing data from migrated VMs before enforcing standards
  - Avoiding enforcement in Phase 1 reduces migration blockers without sacrificing the future path to size governance

---

### ADR 38: VM Eviction Strategy

- **Issue**: The VM eviction strategy determines behavior during node drain — LiveMigrate blocks drains on failure (surfaces capacity problems) while LiveMigrateIfPossible silently shuts down non-migratable VMs.
- **Decision**: `LiveMigrate` for all VMs as the fleet default. `LiveMigrateIfPossible` available as a per-VM override annotation for known non-migratable legacy VMs (e.g., USB passthrough). `None` not used.
- **Status**: Decided (2026-03-05)
- **Assumptions**:
  - Cluster N+1 headroom (ADR 40) is maintained at all times to absorb a node drain without scheduling failures
  - Non-migratable VMs are identified and tagged during triage (ADR 57)
- **Argument**:
  - `LiveMigrate` default surfaces capacity and compatibility problems at drain time rather than allowing silent VM shutdown
  - Per-VM override provides an escape hatch for known non-migratable workloads without compromising the fleet default

---

### ADR 39: Memory Overcommitment Policy

- **Issue**: OCP-V does not overcommit memory by default — this increases hardware requirements vs. VMware but eliminates OOM kill risk; the policy must be set for production and non-production cluster tiers.
- **Decision**: No memory overcommit for production clusters. CPU overcommit only (1.5x) for non-production clusters. wasp-agent with NVMe swap not enabled in Phase 1 (re-evaluate in Phase 2 based on production density data).
- **Status**: Decided (2026-03-05)
- **Assumptions**:
  - Hardware sizing is based on 1:1 VM memory to physical memory allocation for production
  - Non-production CPU overcommit is acceptable given lower SLA requirements
- **Argument**:
  - No memory overcommit for production eliminates OOM kill risk for business-critical VMs
  - CPU overcommit for non-prod improves density at development/test clusters without production risk

---

### ADR 40: Capacity Planning and Right-Sizing Methodology

- **Issue**: Capacity planning must account for live migration headroom, hardware remediation scenarios, pod limits, and upgrade drain windows — a utilization threshold must be defined to trigger action before the cluster becomes over-subscribed.
- **Decision**: N+1 node headroom maintained per cluster at all times (one full node's VMs must be absorbable by remaining nodes). Alert at 70% CPU and 80% memory utilization. Sizing baseline derived from RVTools XLSX export of existing VMware estate.
- **Status**: Decided (2026-03-10)
- **Assumptions**:
  - RVTools data reflects actual VM utilization (not provisioned size)
  - 70% CPU / 80% memory thresholds provide sufficient lead time before headroom is exhausted
- **Argument**:
  - N+1 headroom ensures a node drain (maintenance or FAR remediation) does not cause scheduling failures
  - Percentage-based thresholds are actionable and more meaningful than raw VM counts

---

### ADR 41: Descheduler and VM Rebalancing

- **Issue**: After node drains, VMs are not automatically redistributed — clusters become unbalanced until a descheduler is enabled.
- **Decision**: `KubeVirtRelieveAndMigrate` descheduler profile enabled on all clusters. PSI metrics enabled on all worker nodes. PodDisruptionBudget set to `maxUnavailable: 1` for all VM namespaces to protect against simultaneous descheduler and manual drain.
- **Status**: Decided (2026-03-10)
- **Assumptions**:
  - PSI metrics are available on the host kernel version used by OCP 4.21 worker nodes
  - Descheduler trigger frequency set to 1-hour interval to avoid excessive live migration churn
- **Argument**:
  - `KubeVirtRelieveAndMigrate` is load-aware and avoids rebalancing VMs that would increase imbalance
  - PSI-based load awareness prevents migrating VMs unnecessarily when the cluster is already balanced

---

## Observability & Logging

### ADR 42: OpenShift Logging

- **Issue**: OCP generates multiple log streams that must be forwarded to the enterprise SIEM while providing short-term local searchability for operator troubleshooting.
- **Decision**: LokiStack deployed per cluster with 30-day local retention. ClusterLogForwarder ships all log streams (node, pod, audit) to Splunk via HEC. Audit logs forwarded via a dedicated pipeline separate from application logs.
- **Status**: Decided (2026-03-12)
- **Assumptions**:
  - Splunk HEC endpoint is available and has confirmed ingestion capacity for the fleet log volume
  - LokiStack backed by StorageGRID S3 (DC/campus) or ODF ObjectBucketClaim (branch)
- **Argument**:
  - LokiStack provides local searchability for operators without requiring a Splunk query for every troubleshooting session
  - Dedicated audit log pipeline prevents application log volume spikes from dropping audit events

---

### ADR 43: Metric Retention Days

- **Issue**: Local Prometheus retention is capped by cluster storage — platform teams need short-term metrics for debugging and capacity teams need months of history for trending.
- **Decision**: Local Prometheus 15-day retention per cluster. ACM Thanos federation for fleet-wide aggregation with 90-day retention backed by StorageGRID. Dynatrace provides application-layer long-term metrics independent of OCP Prometheus.
- **Status**: Decided (2026-03-12)
- **Assumptions**:
  - StorageGRID has sufficient capacity for 90-day Thanos metric store across the fleet
  - Dynatrace covers the application observability layer without requiring OCP Prometheus extension
- **Argument**:
  - 15-day local retention provides operator debugging window without excessive cluster storage consumption
  - Thanos federation enables fleet-wide capacity planning and compliance reporting from a single query endpoint

---

### ADR 44: Monitoring and Observability Replacement

- **Issue**: Existing VMware monitoring tools (vROPs/Aria) have no visibility into OCP-V workloads — a replacement observability strategy must be defined before production migration begins.
- **Decision**: OCP-V built-in metrics (~4,600 metrics) via Grafana dashboards on ACM for VM and cluster visibility. AlertManager integrated with ServiceNow for NOC alerting. Dynatrace for application-layer observability. Vendor tools (NetApp, Cisco Intersight) for hardware and storage monitoring. No additional APM tool introduced in Phase 1.
- **Status**: Decided (2026-03-15)
- **Assumptions**:
  - ServiceNow AlertManager integration is available
  - Dynatrace agents are deployed on migrated VMs as part of post-migration runbook
- **Argument**:
  - OCP-V built-in metrics cover VM, node, storage, and network dimensions without additional tooling
  - Integrating AlertManager with ServiceNow preserves the existing NOC workflow without retraining

---

## Cluster Lifecycle & Operations

### ADR 45: Hardware Watchdog — Automated Remediation

- **Issue**: A hung or unreachable node holds VMs hostage — automated hardware-level fencing is required to meet the HA SLA agreed with application owners.
- **Decision**: Fence Agents Remediation (FAR) via Redfish/IPMI BMC for all clusters. Fully automatic fencing — no operator-in-loop gate. NOC alert sent immediately after fence event for awareness. SNR not used (unreliable under network partitions).
- **Status**: Decided (2026-03-15)
- **Assumptions**:
  - Redfish/IPMI is accessible from the cluster network to all node BMCs
  - N+1 headroom (ADR 40) ensures fenced node's VMs can be rescheduled
- **Argument**:
  - FAR provides hardware-level remediation equivalent to vSphere HA — familiar outcome for VM operators
  - Fully automatic fencing minimizes MTTR for hung nodes; NOC alert provides awareness without creating an approval gate in the critical path

---

### ADR 46: maxUnavailable Node Setting

- **Issue**: The default `maxUnavailable: 1` is never written explicitly — a silent platform default that could change in future OCP versions; upgrade duration for large clusters is a concern.
- **Decision**: `maxUnavailable: 1` set explicitly in all MachineConfigPools. Increase to `2` for clusters with ≥16 nodes, subject to change management approval per upgrade event.
- **Status**: Decided (2026-03-15)
- **Assumptions**:
  - Increasing to 2 for large clusters still maintains N+1 VM scheduling headroom
  - Change management approval is achievable within the maintenance window planning window
- **Argument**:
  - Explicit setting prevents unexpected behavior if the platform default changes in a future OCP release
  - Increasing to 2 for large clusters can halve the upgrade window duration — significant at 400-site scale

---

### ADR 47: Cluster Upgrade and Maintenance Window Strategy

- **Issue**: OCP-V upgrades trigger live migrations for all VMs on each drained node — upgrade windows must account for this additional time and be aligned with application SLAs and change moratoriums.
- **Decision**: `workloadUpdateStrategy: LiveMigrate` in HyperConverged CR. Tiered rollout: sandbox → non-prod → production with 7-day bake period between tiers. 4-hour maintenance windows on Sunday 02:00–06:00. Moratorium calendar integrated with change management system.
- **Status**: Decided (2026-03-18)
- **Assumptions**:
  - 4-hour windows are sufficient to drain and upgrade one node with average VM density
  - 7-day bake period between tiers is acceptable to the change management board
- **Argument**:
  - `LiveMigrate` strategy ensures VMs are not interrupted during upgrades — aligns with HA SLA
  - Tiered rollout catches upgrade-related issues in lower environments before production exposure

---

### ADR 48: Node Maintenance and Drain Procedures

- **Issue**: Node maintenance in OCP-V requires standardized procedures that integrate with change management and are familiar to VM operators accustomed to vSphere maintenance mode.
- **Decision**: Node Maintenance Operator (NMO) installed from OperatorHub. `NodeMaintenance` CRs managed via GitOps. Pre-drain AAP job validates N+1 headroom and opens ServiceNow change ticket. Drain procedures documented in runbook aligned to existing ITSM workflow.
- **Status**: Decided (2026-03-18)
- **Assumptions**:
  - NMO is available on OperatorHub for OCP 4.21
  - AAP pre-drain job can query cluster capacity API and interface with ServiceNow
- **Argument**:
  - NMO `NodeMaintenance` CR provides a declarative, Git-tracked maintenance record equivalent to vSphere maintenance mode
  - Pre-drain capacity check prevents drains that would violate N+1 headroom before the operator is aware

---

### ADR 49: NTP / Time Synchronization

- **Issue**: Misconfigured NTP is a common root cause of Kerberos failures, etcd elections, and TLS validation errors — it must be correct before cluster installation and cannot easily be changed post-install.
- **Decision**: Chrony configured via MachineConfig pointing to Acme Corp internal NTP servers before installation. Linux guest VMs sync to host via kvm-clock. Windows guest VMs sync directly to internal NTP servers via their existing time sync policy.
- **Status**: Confirmed (2026-02-10)
- **Assumptions**:
  - Internal NTP servers are reachable from all cluster networks before installation
  - kvm-clock is enabled by default on OCP 4.21 worker nodes
- **Argument**:
  - Pre-install NTP configuration prevents a category of post-install failures that are difficult to diagnose
  - Per-OS-type sync model preserves existing Windows time policy without changes

---

### ADR 50: GitOps Tooling Boundary (Argo CD vs ACM Policies vs AAP)

- **Issue**: Argo CD, ACM Policies, and AAP have overlapping capabilities for cluster configuration — without clear boundaries, conflicting management of the same resources creates drift and complicates incident response.
- **Decision**: Argo CD owns Day 2 cluster configuration (operators, NMState, MachineConfigs, NADs). ACM Policies enforce fleet-wide compliance baselines and upgrade orchestration where Argo cannot reach. AAP handles infrastructure automation (server profile updates, ServiceNow integration, pre/post-migration orchestration). No resource managed by more than one tool.
- **Status**: Decided (2026-03-20)
- **Assumptions**:
  - All three tools are available and operational before production migration
  - Tool ownership boundaries are documented and enforced via team process
- **Argument**:
  - Clear ownership boundaries prevent conflicting reconciliation loops between Argo and ACM
  - AAP's ITSM integration is better suited for imperative infrastructure operations than Argo CD's declarative model

---

### ADR 51: VM Day 2 Lifecycle Management Tooling (GitOps vs AAP)

- **Issue**: Post-migration VM operations (create, delete, resize, reboot, patch orchestration) require a defined management tool — this is distinct from cluster configuration tooling (ADR 50) and determines the automation backlog and team training scope.
- **Decision**: Hybrid model. Argo CD manages desired-state VM specs (create/delete/resize via PR workflow in Git). AAP handles imperative operations (reboot, patch orchestration, ServiceNow ticket lifecycle). Clear boundary documented: Argo CD owns VM manifests; AAP owns operational actions.
- **Status**: Decided (2026-04-01)
- **Assumptions**:
  - Argo CD PR workflow is acceptable to VM operators for create/delete/resize operations
  - AAP playbooks for reboot and patch orchestration can interface with ServiceNow ITSM
- **Argument**:
  - GitOps for VM specs provides drift detection, audit trail, and change history for all VM configurations
  - AAP for imperative operations mirrors the existing Ansible-based VMware management model familiar to the team

---

## Migration

### ADR 52: Primary VM Migration Method

- **Issue**: Cold vs. warm migration must be standardized before waves begin — both methods require different planning, network configuration, and change management windows.
- **Decision**: Cold migration as the default for all tiers. Warm migration available by exception only for workloads requiring <2h downtime window; exception requires architecture sign-off. MTV warm migration network pre-provisioned and validated in sandbox.
- **Status**: Decided (2026-03-25)
- **Assumptions**:
  - Most workloads have acceptable downtime windows for cold migration
  - Warm migration network (dedicated VLAN) is available and validated before any warm migration wave
- **Argument**:
  - Cold migration is simpler, lower-risk, and does not require a dedicated migration network for every site
  - Warm migration by exception ensures the complexity is only introduced where the application SLA demands it

---

### ADR 53: Where Can We Store MTV Plan Artifacts?

- **Issue**: MTV migration plan CRs contain credential references and provider connection details — storing them in Git risks exposing credentials.
- **Decision**: MTV plan CRs stored in a sealed namespace on the destination OCP-V cluster. vCenter credentials stored in Vault; referenced at runtime by External Secrets Operator. Plan templates version-controlled in Git without credentials.
- **Status**: Decided (2026-03-25)
- **Assumptions**:
  - Vault is reachable from the destination cluster during migration execution
  - External Secrets Operator can inject vCenter credentials at MTV plan runtime
- **Argument**:
  - Separating plan templates (Git) from credentials (Vault) enables version control without credential exposure
  - Sealed namespace limits plan CR access to the migration operations team

---

### ADR 54: Windows VM Post-Migration Strategy

- **Issue**: MTV does not automatically remove VMware Tools or install the QEMU guest agent on Windows VMs — a scalable, automated post-migration remediation path is required for the Windows fleet.
- **Decision**: Mandatory AAP playbook for all Windows VMs post-migration: remove VMware Tools, install QEMU guest agent, verify VirtIO drivers, run baseline connectivity check. No Windows VM signed off without playbook completion. Playbook runs within the same maintenance window as migration.
- **Status**: Decided (2026-03-28)
- **Assumptions**:
  - AAP has network access to migrated Windows VMs via WinRM/SSH
  - QEMU guest agent MSI is hosted in Nexus and accessible from all clusters
- **Argument**:
  - Automated playbook ensures consistency across 100s of Windows VMs — manual remediation does not scale
  - Running within the same maintenance window minimizes the holdback period before sign-off

---

### ADR 55: Guest OS Lifecycle Management (In-Guest Patching)

- **Issue**: Enterprise patching tools (WSUS, SCCM, Satellite) and EDR agents must remain operational after hypervisor migration — any VMware-specific hooks need to be removed first.
- **Decision**: WSUS, SCCM, and Red Hat Satellite operate unchanged post-migration — VM VLAN connectivity is preserved (ADR 14). VMware Tools hooks removed by post-migration playbook (ADR 54). Sandbox pilot validates full SCCM/WSUS/Satellite cycle and EDR scan before Wave 1.
- **Status**: Decided (2026-03-28)
- **Assumptions**:
  - Patching tools communicate over the network and have no VMware vSphere API dependencies
  - Sandbox pilot includes a representative sample of Windows and Linux VM types
- **Argument**:
  - Network-based patching tools are hypervisor-agnostic; no reconfiguration required after migration
  - Sandbox validation before Wave 1 prevents discovering incompatibilities at production scale

---

### ADR 56: Post-Migration Validation Framework

- **Issue**: Without a standardized validation checklist, VMs may be declared healthy before application-level issues surface — a consistent sign-off process is required before each wave closes.
- **Decision**: Mandatory post-migration checklist: QEMU guest agent status, VirtIO driver verification, network connectivity (ping, DNS, app port), application health check, storage IOPS baseline. Source VMware VMs held powered-off for 14-day holdback before deletion. App-owner + platform team co-sign-off required for wave closure.
- **Status**: Decided (2026-04-01)
- **Assumptions**:
  - Application owners are available and engaged during migration wave windows
  - 14-day holdback period is acceptable to the change management board
- **Argument**:
  - Mandatory checklist ensures no VM is signed off without a minimum set of health checks
  - 14-day holdback provides a recovery window if application issues surface after initial sign-off

---

### ADR 57: Migration Workload Triage and Wave Planning

- **Issue**: Not all VMware VMs are candidates for migration — EOL OS, unsupported appliances, and unused VMs must be identified before waves are planned to avoid migrating non-viable workloads.
- **Decision**: Triage scoring applied to all VMs: EOL OS → rebuild, unsupported appliance → evaluate replacement, unused VM → decommission. Wave composition by application group and criticality tier. Wave 0 = dev/test only. All waves require architecture review and change management approval.
- **Status**: Decided (2026-04-01)
- **Assumptions**:
  - RVTools provides the initial VM inventory for triage scoring
  - Application group ownership data is available from the CMDB
- **Argument**:
  - Starting with dev/test in Wave 0 builds team confidence and surfaces tooling issues before production exposure
  - Application-group-based wave composition ensures dependent VMs migrate together, reducing post-migration dependency failures

---

### ADR 58: MTV Controller Placement and Migration Network

- **Issue**: MTV forklift-controller placement and migration network bandwidth must be defined before waves begin — insufficient bandwidth or resource contention on the destination cluster will extend migration windows.
- **Decision**: MTV forklift-controller scheduled on worker nodes (not masters). Dedicated 10GbE migration VLAN configured before Wave 1. Maximum 10 concurrent migrations per wave enforced via MTV concurrent limit setting. VDDK hosted in Nexus container registry.
- **Status**: Decided (2026-04-01)
- **Assumptions**:
  - Dedicated migration VLAN is available and routed from vCenter/ESXi to destination OCP-V clusters
  - VDDK image version is compatible with vCenter version in use
- **Argument**:
  - Worker node placement avoids resource competition between MTV and control plane during peak migration activity
  - 10 concurrent migration limit is calibrated to avoid saturating the dedicated migration VLAN

---

### ADR 59: OpenShift Virtualization Operator Baseline (HCO / CDI / VM Workload Updates)

- **Issue**: HyperConverged Cluster Operator settings span multiple day-2 concerns — without a single baseline committed to GitOps, settings drift across clusters and upgrade behavior becomes inconsistent.
- **Decision**: One HCO spec fragment per cluster class (DC, campus, branch) committed to GitOps. Settings: ODF default storage class for VM disks, `workloadUpdateStrategy: LiveMigrate` (ADR 47), `DeclarativeHotplugVolumes` feature gate enabled (ADR 20), VNC TLS enabled, console exposure limited per ADR 33. Baseline validated in sandbox on OCP 4.21 before production rollout.
- **Status**: Decided (2026-04-05)
- **Assumptions**:
  - GitOps Argo CD manages HCO CR alongside other cluster Day 2 configuration
  - Cluster class differences are limited to storage class and network interface references
- **Argument**:
  - Git-tracked HCO baseline enables drift detection and consistent upgrade behavior across the fleet
  - Per-cluster-class fragments allow site-type variations without forking the entire baseline

---

### ADR 60: VM Golden Images, Boot Sources, and DataSources

- **Issue**: New VM provisioning after migration requires a defined golden image catalog — ad-hoc image imports create security scanning gaps and unsupported OS combinations.
- **Decision**: Red Hat provided RHEL and Windows DataSources mirrored to Nexus. Golden images owned and maintained by the platform team. VirtIO-win ISO hosted in Nexus. Cloning permissions via `vm-operator` ClusterRole (ADR 29). Quarterly image refresh cadence with security scan gate before promotion.
- **Status**: Decided (2026-04-05)
- **Assumptions**:
  - Nexus is accessible from all cluster types for image pull
  - Quarterly cadence meets patch currency requirements agreed with InfoSec
- **Argument**:
  - Centralized catalog with mandatory security scan gate prevents unsupported or unpatched images entering the fleet
  - Quarterly refresh is frequent enough to meet patch requirements without excessive operational overhead

---

### ADR 61: CPU / NUMA / Dedicated Resources for Performance-Sensitive VMs

- **Issue**: A small number of latency-sensitive workloads may require CPU pinning or huge pages — but enabling these fleet-wide adds scheduling complexity and conflicts with live migration.
- **Decision**: NUMA topology awareness enabled fleet-wide (low overhead, no migration impact). CPU pinning and huge pages by exception only — requires architecture + InfoSec sign-off and a documented live-migration posture (typically `LiveMigrateIfPossible` or `None` for pinned VMs). Default: no dedicated CPUs, no huge pages.
- **Status**: Decided (2026-04-05)
- **Assumptions**:
  - NUMA topology awareness is compatible with `LiveMigrate` default strategy
  - Exception process can be completed within standard change management timelines
- **Argument**:
  - Default of no pinning/huge pages keeps the fleet on the standard scheduling model with full live migration support
  - Exception process with sign-off ensures performance tuning is only applied where justified and the migration posture is explicitly documented

---

### ADR 62: SR-IOV, GPU, and PCI Passthrough Policy

- **Issue**: PCI passthrough (SR-IOV, GPU, USB) disables live migration for affected VMs — a fleet-wide policy is needed to avoid scheduling conflicts with the standard migratable estate.
- **Decision**: No SR-IOV, GPU, or PCI passthrough for standard migrated VMs. Exceptions require a dedicated node pool and architecture review. USB passthrough not supported in production. Exception process aligned with change management.
- **Status**: Decided (2026-04-05)
- **Assumptions**:
  - No migrated VMs in the initial estate require SR-IOV or GPU passthrough
  - Dedicated node pools for future passthrough workloads can be provisioned without disrupting the standard fleet
- **Argument**:
  - Keeping the bulk of the fleet on the standard model maximizes live migration coverage
  - Dedicated node pool isolation prevents passthrough scheduling constraints from impacting standard VM placement

---

### ADR 63: Guest NIC Name Preservation Strategy During Migration

- **Issue**: VMware to OCP-V migration can alter Linux guest interface names when the driver changes — workloads with static network configs tied to interface names may lose connectivity.
- **Decision**: NIC name preservation not required fleet-wide. MTV/virt-v2v default conversion accepted. Post-migration validation gate (ADR 56) surfaces affected workloads. Per-VM udev remediation available as a documented exception path for workloads where interface name preservation is required.
- **Status**: Decided (2026-06-30)
- **Assumptions**:
  - Network identity is satisfied by IP/MAC/DNS preservation — interface name string is not a dependency for most workloads
  - Post-migration validation gate (ADR 56) reliably detects connectivity failures before sign-off
- **Argument**:
  - Fleet-wide NIC name preservation adds pre-migration guest remediation overhead that is not justified for most workloads
  - Exception path covers the rare case where a workload has a hard dependency on a specific interface name

---

### ADR 64: MTV Migration Hooks vs AAP-Orchestrated Remediation

- **Issue**: Pre/post-migration automation can run inside MTV migration hooks or via external AAP orchestration — the choice affects ownership, retry behavior, audit integration, and operational complexity across waves.
- **Decision**: Hybrid. MTV hooks for lightweight, in-flight actions tightly coupled to VM cutover (QEMU guest agent install, quick connectivity check). AAP for multi-step remediation, approval gates, and ServiceNow ticket lifecycle. Boundary documented: hooks run during the MTV workflow; AAP runs after MTV reports success.
- **Status**: Decided (2026-06-30)
- **Assumptions**:
  - MTV hook capability is available and stable in the MTV release used for production waves
  - AAP can be triggered by MTV success event via webhook or scheduled AAP job
- **Argument**:
  - MTV hooks for lightweight actions keep simple remediation close to the migration event without external dependencies
  - AAP for complex multi-step remediation provides retry logic, ITSM integration, and audit trails not available in MTV hooks

---

### ADR 65: Partial Wave Failure Handling Policy

- **Issue**: In large migration waves, some VMs will fail — without a defined policy, wave closure decisions become ad-hoc and inconsistent across teams, increasing operational risk.
- **Decision**: Wave closure requires ≥95% VM success. Failed VMs documented and deferred to the next migration window. Rollback triggered if >25% of a wave fails in a single window. Holdback clock (14 days, ADR 56) starts at wave closure sign-off, not at individual VM migration. App-owner + platform team co-sign-off required for both closure and deferred VM acceptance.
- **Status**: Decided (2026-06-30)
- **Assumptions**:
  - 95% success threshold is acceptable to application owners and the change management board
  - Deferred VMs can be scheduled in the next available maintenance window without SLA impact
- **Argument**:
  - Formal policy removes ambiguity during high-pressure cutover windows and ensures consistent wave outcomes across teams
  - 25% rollback trigger limits the blast radius of a problematic wave before it consumes the entire maintenance window

---
