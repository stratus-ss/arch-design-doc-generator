# Acme Corp OCP-V — Architecture Decision Record

---

## Installation & Provisioning

### ADR 1: On-Prem Cluster Installation Host (Bastion)

- **Issue**: Installation method and bastion requirements vary significantly between IPI, Agent-based, Assisted Installer, and ACM ZTP. Key differentiators include provisioning network requirements, BMC access model, disconnected/air-gapped support, and automation scalability. Must be decided independently for hub clusters and spoke/edge clusters, as scale and operational model differ between them.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 2: On-Prem OpenShift Version

- **Issue**: Target OCP version must be selected before installation and affects support lifecycle, feature availability, and third-party operator compatibility. Tracking the latest GA (N) provides the broadest feature set but requires a faster upgrade cadence; N-1 is more conservative. Version selection may be constrained by dependencies on specific operator or partner features not yet GA on older releases.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 3: Initial Cluster Network CIDRs and Pod Limits

- **Issue**: Pod subnet, service subnet, and host CIDR must be finalized before installation — they cannot be changed post-install without a full cluster rebuild. CIDRs must not conflict with existing infrastructure. Pod-per-node limit (default 250) must account for VM density plus system pods and sidecars; insufficient limits can prevent VM scheduling. If the same non-routable ranges are reused across clusters, fleet management is simplified but per-site IP planning is required where dedicated OCP subnets are unavailable.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 4: Pull Through Container Image Cache

- **Issue**: A pull-through image cache reduces dependency on public registries, avoids rate limiting (Docker Hub, Quay.io), and supports partially disconnected or air-gapped deployments. Must decide which registry product serves as the cache, whether it is available to all cluster types (DC, edge, branch), and how disconnected sites obtain images when the cache is unreachable.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 5: ACM Hub Topology

- **Issue**: A single ACM hub simplifies management but creates a large blast radius and may not align with organizational boundaries (e.g., separate DC vs. edge teams). Split hubs provide operational isolation and team alignment but lose unified visibility. At large fleet scales, active/passive standby for each hub must also be evaluated — noting that an ACM outage does not affect running workloads, only management operations.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 6: Branch Cluster Architecture

- **Issue**: Edge and branch sites require a standardized compact cluster architecture that fits within constrained hardware (typically 3 nodes). Storage must be local (ODF on NVMe) since centralized storage is unavailable or impractical. Remote provisioning method, ODF replication factor, IP space, and bandwidth constraints for image pulls must all be decided before rollout at scale.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 7: Host Firmware, BIOS, and CPU Vulnerability Baseline

- **Issue**: CIS and hardening guidance reference firmware settings (e.g., Intel TXT posture) and verification of CPU mitigations that are not visible from within the OS. Server profile templates from {HW_MGMT_PLATFORM} should enforce approved BIOS/firmware revisions per the hardware standard. A vendor-recommended virtualization BIOS profile should be validated against OCP foundation requirements (VT-x, VT-d, SR-IOV if applicable). Pre-flight checks (manual or automated) are recommended before installation to validate firmware, BIOS, and server management versions are consistent across nodes. Not required for sandbox but should be in place before production deployments.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

## Network & Connectivity

### ADR 8: OpenShift Network Card Naming Consistency

- **Issue**: On certain NIC models, interface names can change across reboots due to PCIe enumeration order, causing NMState policies and NAD definitions to reference the wrong interface. This must be resolved before production deployment as it can cause silent network misconfiguration on node restart.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 9: OpenShift STP and BPDUs

- **Issue**: Linux Bridge transmits BPDUs by default, triggering BPDUguard on upstream switch ports and causing port shutdown. OVS Bridge does not send BPDUs and provides native VLAN trunk handling. The bridge type for VM data traffic must be decided, as it affects switch port configuration and VLAN tagging behavior for guest VMs.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 10: NADs Limited To Namespaces or Cluster Wide?

- **Issue**: NetworkAttachmentDefinitions (NADs) that map VLANs to OVS bridges can be created in a specific namespace (scoped) or in the default namespace (cluster-wide). Namespace-scoped NADs provide isolation but require duplication across namespaces and add onboarding complexity. Cluster-wide NADs simplify provisioning but rely on cluster-level security tier separation rather than namespace-level controls.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 11: Create All Presented VLANs or Only Those In Use

- **Issue**: The number of VLANs trunked to a node may exceed what is currently in use by workloads. Pre-configuring NMState policies and NADs for all presented VLANs at build time avoids post-deployment updates when new workloads require a VLAN that was not pre-configured. However, it adds upfront work and requires all required VLANs to be known at build time.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 12: OpenShift Node vNIC Layout

- **Issue**: The number and role of vNICs per node must be decided before server profile templates are finalized. A minimum of 2 vNICs (management/OCP + VM data traffic) is common, but a 3rd or 4th vNIC may be warranted for dedicated live migration, backup, or observability traffic — especially at 100G where a single pipe can handle all traffic with QoS, but separation improves operational visibility. This decision feeds directly into NMState policies, NAD definitions, and server profile templates and is difficult to change post-deployment. Site types (DC, campus, branch) may justify different vNIC counts given differences in hardware management models, bandwidth, and VM density.

#### ADR 12.1: Data Center (DC) vNIC Layout

- **Issue**: DC clusters typically use Fabric Interconnect-managed hardware with high-bandwidth networking and full rack spread. vNIC count and role assignment must be finalized before server profile templates are created.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

#### ADR 12.2: Campus Site vNIC Layout

- **Issue**: Campus sites may use standalone rack servers managed by a hardware management platform rather than Fabric Interconnects. The vNIC layout must reflect this hardware model while preserving traffic separation intent from the DC design.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

#### ADR 12.3: Branch vNIC Layout

- **Issue**: Branch clusters are typically constrained-hardware 3-node compact sites with low VM density and limited bandwidth. Dedicated live migration and backup vNICs may not be justified — the vNIC layout must balance traffic isolation against management overhead at scale.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 13: Load Balancing Strategy

- **Issue**: OCP clusters require VIPs for the API server and ingress router. The built-in keepalived/haproxy handles this without external dependencies; an external load balancer (e.g., F5) provides additional features but introduces a provisioning dependency and potential point of failure. Must also clarify whether the existing DNS/GTM infrastructure intercepts OCP traffic or passes through directly.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 14: VM IP Address Management (IPAM) Strategy

- **Issue**: VMs attached to secondary networks via NAD/OVS bridges rely on existing DHCP/DNS infrastructure for IP assignment. MAC address preservation during migration is critical — existing DHCP reservations are keyed to MAC addresses. Static IP VMs require manual post-migration verification. The strategy must confirm that no IP changes occur during migration, as IP changes can break application dependencies, monitoring, and access control lists.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 15: Network Policy and Microsegmentation for VMs

- **Issue**: VMs attached to bridged VLANs (secondary networks) are not subject to Kubernetes NetworkPolicy — existing VLAN and firewall segmentation applies directly. NetworkPolicy only affects traffic on the pod network. Must determine whether any VMs will use the pod network, and whether enterprise microsegmentation tools (e.g., Illumio) have any applicability to OCP-V workloads.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 16: VM Service Exposure Strategy

- **Issue**: Migrated VMs can be reached via direct VLAN connectivity (preserving the existing network path with no client-side changes), via a Kubernetes Service (adds an abstraction layer and enables load balancing), or via an OpenShift Route (for HTTP/HTTPS workloads). For lift-and-shift migrations, direct VLAN reachability is the lowest-risk option and eliminates the need for MetalLB or service abstractions.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 17: Cluster-wide Proxy and Egress Configuration

- **Issue**: A cluster-wide proxy requires maintaining noProxy exception lists across every cluster, which becomes a significant operational burden at fleet scale. Firewall-only egress eliminates this but requires firewall rules to be in place before installation. VM traffic on bridged VLANs bypasses the cluster proxy entirely — this must be understood by network and security teams. Branch/edge cluster egress may differ from DC clusters depending on available connectivity (proxy, SD-WAN DIA, etc.).
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

## Storage & Backup/DR

### ADR 18: Object Storage for On-Prem Clusters

- **Issue**: Multiple OCP-V platform components require S3-compatible object storage: the internal image registry, Loki log retention, and Prometheus/Thanos long-term metrics. Not all sites may have local S3-compatible storage available. Remote object storage introduces latency and WAN bandwidth considerations for log/metric flushing. Branch and edge sites may require a different strategy than DC/Regional sites.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 19: Backup and Disaster Recovery Strategy (Cross-Site)

- **Issue**: OCP-V has no built-in equivalent to vSphere Site Recovery Manager (SRM). DR must be composed from a combination of backup tools, storage replication (e.g., async block replication between sites), and application-level DR strategies. Backup frequency must align with application recovery tiers rather than a single blanket policy. The strategy must address DC-to-DC failover, branch cluster data protection, and the absence of an orchestrated cross-site failover mechanism.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 20: PVC Hot-Expand and CD-ROM Hot-Plug

- **Issue**: PVC hot-expand (expanding a VM disk without a reboot) is one of the most frequent day-2 VM operations. Behavior varies by OCP version and CSI driver — the guest OS must recognize the expanded block device without a VM restart, though filesystem expansion inside the guest still requires manual steps. CD-ROM/ISO hot-plug (mounting/unmounting ISOs without powering off) requires the `DeclarativeHotplugVolumes` feature gate, which may be Tech Preview depending on the OCP release. Both must be validated in the target version before migration waves begin.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

## Security & Compliance

### ADR 21: Secret Management and Automation Tooling

- **Issue**: GitOps tooling (Argo CD, AAP) and cluster bootstrapping require secrets at deploy time. Manual secret pre-population is viable short-term but does not scale across a large cluster fleet. Acme Corp enterprise secret manager integration with OpenShift may be incomplete or require a connector layer (e.g., External Secrets Operator). A fallback plan and time-boxed integration effort should be defined to avoid indefinite manual secret management.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 22: On-Prem etcd Database Encryption

- **Issue**: etcd stores all cluster state including Secrets in plaintext by default. Enabling native at-rest encryption addresses compliance requirements (CIS benchmark, InfoSec database encryption standards) but adds ~1-2% performance overhead and requires key rotation procedures and secure key storage. Encrypting only the backup (e.g., GPG before S3 upload) addresses the data-at-rest-in-storage concern but does not satisfy requirements that mandate database-level encryption.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 23: Kubeadmin and/or Breakglass Account

- **Issue**: If the primary identity provider (LDAP/OIDC) is unavailable, cluster administrators must still be able to access clusters for emergency operations. A local breakglass account (htpasswd) provides this fallback but its credentials must be stored securely, retrieved only under controlled conditions, and rotated on a schedule. The default `kubeadmin` account should be evaluated — it may be disabled after initial setup depending on the security posture.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 24: Kubeconfig Storage

- **Issue**: The `kubeconfig` generated during cluster installation contains client certificates that grant cluster-admin-equivalent access. Loss or unauthorized access to this file is equivalent to a full cluster compromise. At fleet scale, hundreds of kubeconfig files must be stored, rotated, and retrievable under break-glass conditions. Storage must be audited and access logged.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 25: TLS/SSL Certificate Strategy

- **Issue**: Default OCP self-signed certificates cause TLS warnings and may not meet enterprise compliance requirements. API server certificates and ingress wildcard certificates should be replaced with enterprise or internal CA-signed certificates. At fleet scale (many clusters × many routes each), manual certificate management is not viable — cert-manager automation or a similar solution is required. The internal CA model (wildcard vs. per-route, sub-CA delegation) must be aligned with the enterprise certificate team.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 26: CIS Benchmark Compliance Scope

- **Issue**: Separate CIS benchmarks exist for OCP and OCP-V — both may need to be evaluated. Auto-remediation via the Compliance Operator can cause node reboots and must be coordinated with maintenance windows; scan-then-manually-remediate is safer in regulated environments. The enterprise scanning tool (e.g., Tenable, ACS) may or may not have a dedicated OCP-V benchmark profile, which affects the remediation workflow.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 27: Audit Logging Policy

- **Issue**: OCP provides four audit profiles — Default (metadata only), WriteRequestBodies (evidence of changes), AllRequestBodies (evidence of reads and changes), and None. Higher verbosity provides better forensic coverage for PCI/InfoSec compliance but significantly increases log volume across a large cluster fleet. The profile must be aligned with the SIEM/log aggregation team's capacity and the compliance framework's specific requirements.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

## RBAC, Namespaces & Access

### ADR 28: Project Naming Convention for VMs

- **Issue**: Namespace naming granularity determines RBAC boundaries, resource quota scope, and NAD visibility. OS-level namespaces (e.g., linux-vms, windows-vms, appliance-vms) are simple and mirror VMware cluster organization. App-level or business-unit namespaces provide finer RBAC control but increase operational overhead and the number of namespaces to manage. The decision is tightly coupled with ADR 29 (RBAC model) and ADR 30 (VM placement).
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 29: OpenShift RBAC Assignments

- **Issue**: Multiple teams require different levels of access to OCP-V clusters — platform admins, OS teams (Windows/Linux), backup operators, app owners, and read-only observers. LDAP group sync, privileged access management (PAM) connectors, and break-glass procedures all need to be defined. Custom ClusterRoles are required for use cases (e.g., backup tool RBAC, VM console access) not covered by built-in roles. An iterative approach — deploy minimal role, audit API logs for denied actions, refine — is recommended over trying to define all roles upfront.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 30: Location in OpenShift for Migrated VMs

- **Issue**: Migrated VMs must be assigned to namespaces in a way that aligns with operational teams, security tiers, and RBAC boundaries. The strategy must define whether security tier separation (e.g., DMZ, standard, dedicated) remains at the cluster level or is also reflected in namespace organization. This decision is directly dependent on ADR 28 (naming convention) and ADR 29 (RBAC model) and should be finalized before migration waves begin.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 31: Self Provisioner Disabled?

- **Issue**: By default, any authenticated OCP user can create projects (namespaces). In a VM-focused environment, namespace creation should be controlled and follow the same ticket-based or GitOps-driven provisioning model used for VMware. Unrestricted self-provisioning can lead to namespace sprawl, ungoverned resource consumption, and inconsistent RBAC application.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 32: Resource Quotas and Limit Ranges for VM Namespaces

- **Issue**: Kubernetes ResourceQuota objects can cap CPU, memory, and object counts per namespace. When quotas are active, OCP-V auto-sets VM memory limits to 2x requested and CPU limits to 1 per vCPU — this may not reflect actual VM sizing and can cause unexpected scheduling failures. Each virt-launcher pod also carries overhead (~100–300 MiB) that counts against quota. Must decide whether the operational benefit of quota enforcement outweighs the configuration complexity for VM namespaces.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 33: VM Console and Remote Access Strategy

- **Issue**: OCP-V provides multiple VM access methods: VNC via the web console, virtctl SSH, virtctl serial console, and direct RDP/SSH over bridged VLANs. Broad console access increases the attack surface; most VM users should access VMs via SSH/RDP (same as VMware today). RBAC on `subresources.kubevirt.io` resources controls console access at a granular level. A per-team access matrix must be defined, and session recording requirements should be evaluated for any role that retains console access.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

## VM Configuration & Scheduling

### ADR 34: On-Prem Control Plane Node Placement

- **Issue**: etcd quorum requires a majority of control plane nodes to remain healthy simultaneously. Control plane nodes must be distributed across independent failure domains (separate chassis, racks, and power circuits) to prevent a single hardware failure from taking down quorum. For compact (3-node) clusters at edge/branch sites, cross-rack distribution is not possible — this risk must be accepted or mitigated differently.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 35: Control Plane To Host Infrastructure Load

- **Issue**: OCP-V supports schedulable masters that can host both control plane components and end-user workloads, eliminating the need for dedicated infra nodes. However, without dedicated infra nodes, platform services (ingress, monitoring, logging) share resources with VMs. Noisy-neighbor labels can be used to protect etcd from resource-intensive workloads on the same node, but the boundary must be explicitly defined.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 36: VM Hot-Plug Configuration

- **Issue**: OCP-V supports hot-plugging additional CPU sockets and memory to a running VM within pre-defined ratios (default: 4x CPU sockets, 2x memory) without requiring a VM reboot. Requests that exceed these ratios require a guest restart. The default ratios must be validated as sufficient for the workload profile, as changing them later requires a VM restart for each affected VM.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 37: VM Instance Types and Sizing Standards

- **Issue**: OCP-V supports `VirtualMachineInstancetype` and `VirtualMachinePreference` CRs to define standardized VM size catalogs. Enforcing instance types simplifies capacity planning and prevents VM sizing sprawl. However, if the existing provisioning workflow already handles sizing (e.g., via ServiceNow/ticketing), introducing a catalog adds a change process layer. Admission control enforcement vs. advisory-only must also be decided.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 38: VM Eviction Strategy

- **Issue**: The VM eviction strategy determines behavior when a node is drained for maintenance or upgrade. `LiveMigrate` blocks the drain if migration fails — surfacing capacity and compatibility problems but potentially delaying cluster upgrades. `LiveMigrateIfPossible` silently shuts down non-migratable VMs. `None` causes immediate shutdown. The choice reflects the organization's tolerance for upgrade delays vs. unexpected VM downtime, and can be set per-VM as an override.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 39: Memory Overcommitment Policy

- **Issue**: Unlike VMware, OCP-V does not overcommit memory by default — VM memory requests equal physical memory allocation. This eliminates OOM kill risk but reduces VM density and increases hardware requirements relative to a VMware baseline. Options include no overcommit, controlled memory overcommit via wasp-agent with swap on NVMe (OCP 4.18+), or CPU overcommit only (safe — throttles rather than kills). Policy may differ by cluster tier (prod vs. non-prod).
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 40: Capacity Planning and Right-Sizing Methodology

- **Issue**: Capacity planning must account for live migration headroom (minimum one node's worth of spare capacity to absorb a drained node's VMs), hardware remediation scenarios (automated BMC remediation may reboot a node unexpectedly), pod-per-node limits, and upgrade drain windows. Percentage-based utilization thresholds (e.g., trigger action at 70% CPU) are more actionable than raw VM count targets. Inventory data from the existing VMware environment provides the sizing baseline.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 41: Descheduler and VM Rebalancing

- **Issue**: After node drains and maintenance, VMs are not automatically redistributed — the Kubernetes scheduler only places workloads at scheduling time, not retroactively. The Kube Descheduler Operator can trigger live migrations to rebalance VM workloads across nodes. Two profiles are relevant for OCP-V: `LongLifecycle` (simpler, no prerequisites) and `KubeVirtRelieveAndMigrate` (load-aware, requires PSI metrics enabled on worker nodes). Profile selection must account for hard vs. soft affinity/anti-affinity rule handling and interaction with PodDisruptionBudgets.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

## Observability & Logging

### ADR 42: OpenShift Logging

- **Issue**: OCP generates multiple log streams: node system logs, container/pod stdout, and API audit logs. Vector + ClusterLogForwarder can ship logs to an external SIEM or log platform (e.g., Splunk via HEC). A local LokiStack provides short-term searchable retention for operator troubleshooting without requiring a trip to the external platform. Log volume per node must be estimated to size Loki storage and validate SIEM ingestion capacity before production deployment.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 43: Metric Retention Days

- **Issue**: Local Prometheus retention consumes cluster storage and has a practical cap (typically 7–15 days). Platform/operations teams require short-term data for debugging; capacity planning and performance troubleshooting teams require weeks to months of history. Longer retention requires a central aggregator (ACM Thanos, enterprise APM) backed by object storage. Retention policy may also be influenced by compliance requirements and whether an enterprise observability platform is being onboarded in parallel.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 44: Monitoring and Observability Replacement

- **Issue**: VMware-specific monitoring tools (e.g., Aria/vROPs) have no visibility into OCP-V workloads. OCP-V ships ~4,600 built-in metrics covering VM, node, storage, and network dimensions. A unified observability strategy must cover: VM and cluster metrics (Grafana/Perses on ACM), alerting and NOC integration (AlertManager → ITSM), hardware/storage monitoring (vendor tools that may have beta OCP-V support), and long-term metric storage. An enterprise APM tool may unify these if onboarded on a compatible timeline.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

## Cluster Lifecycle & Operations

### ADR 45: Hardware Watchdog — Automated Remediation

- **Issue**: Without automated node remediation, a hung or unreachable node holds VMs hostage until manually rebooted, which can take minutes to hours. Software Node Remediation (SNR) uses a watchdog process — unreliable under network partitions. Fence Agents Remediation (FAR) uses Redfish/IPMI via the BMC to physically fence the node, providing reliable hardware-level remediation equivalent to vSphere HA. The degree of automation (fully automatic vs. operator-in-the-loop) must be decided based on risk tolerance, as automated remediation can reboot a node even when VMs are still functional but the heartbeat is lost.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 46: maxUnavailable Node Setting

- **Issue**: The `maxUnavailable` setting in the MachineConfigPool controls how many nodes can be updating simultaneously during a cluster upgrade. The default of 1 is never explicitly written to the cluster config — querying the cluster returns empty and the platform silently applies 1. An explicit setting prevents unexpected behavior if the platform default ever changes. For large clusters (16+ nodes), increasing this value to 2–3 can significantly reduce the total upgrade window duration.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 47: Cluster Upgrade and Maintenance Window Strategy

- **Issue**: OCP-V upgrades drain nodes one at a time, triggering live migrations for all VMs on each node before the node updates. With many VMs per node, a single node drain can take significantly longer than a container-only platform upgrade. `workloadUpdateStrategy` in the HyperConverged CR controls whether VMs are live-migrated or evicted during upgrades. A tiered rollout sequence (sandbox → non-prod → prod) with bake periods between tiers reduces production risk. Upgrade windows must account for moratoriums and change management requirements.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 48: Node Maintenance and Drain Procedures

- **Issue**: The Node Maintenance Operator (NMO) provides a declarative, GitOps-compatible maintenance mode that mirrors the vSphere maintenance mode experience — it is more familiar to VM operators than imperative CLI drain commands. NMO is no longer bundled with OCP-V (removed in OCP 4.11) and must be installed from OperatorHub. Node drain procedures must be standardized and integrated with the change management system (e.g., ServiceNow) to ensure pre-drain capacity checks and ticket lifecycle are handled consistently.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 49: NTP / Time Synchronization

- **Issue**: Misconfigured or missing NTP is a common root cause of Kerberos authentication failures, log correlation errors, TLS certificate validation issues, and etcd election problems. Chrony must be configured via MachineConfig to point to Acme Corp internal NTP servers before cluster installation — it cannot be easily changed post-install without a MachineConfig rollout. Guest VMs may sync to the host via kvm-clock or directly to NTP servers; this must be defined per OS type.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 50: GitOps Tooling Boundary (Argo CD vs ACM Policies vs AAP)

- **Issue**: Argo CD, ACM Policies, and AAP have overlapping capabilities for cluster configuration and lifecycle management. Using all three without clear boundaries creates conflicting management of the same resources and makes it difficult to trace where configuration is being applied. The boundary must be explicitly defined: Argo CD for Day 2 cluster config via GitOps; ACM policies for cross-cluster enforcement where Argo cannot (e.g., fleet-wide upgrades); AAP for infrastructure automation and ITSM integration. Acme Corp teams have varying OpenShift experience and existing tool investments that should inform the adoption sequence.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 51: VM Day 2 Lifecycle Management Tooling (GitOps vs AAP)

- **Issue**: Post-migration, VM lifecycle operations (create, delete, resize, snapshot, reboot, patch orchestration) require a defined management tool. Options are GitOps (Argo CD managing VM manifests declaratively in Git), AAP/Ansible (playbook-driven automation integrated with ServiceNow, mirroring existing VMware operational model), or a hybrid. The decision determines the automation backlog scope, team training investment, and the integration surface with ServiceNow/ITSM. This is distinct from ADR 50 (platform/cluster configuration tooling) — ADR 50 defines how the platform itself is configured; this ADR defines how VMs running on the platform are operationally managed day-to-day.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

## Migration

### ADR 52: Primary VM Migration Method

- **Issue**: MTV supports cold migration (VM powered off, disk copied, restarted on OCP-V — simple but requires a downtime window) and warm migration (disk copied while running with incremental syncs, then a brief cutover — less downtime but requires a dedicated migration network and more complexity). The default method and the criteria for exceptions (based on application tier, RPO, or HA capability) must be standardized before migration waves begin to ensure consistent planning and change management.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 53: Where Can We Store MTV Plan Artifacts?

- **Issue**: MTV migration plan CRs can reference vCenter credentials, provider connection details, and network/storage mappings. Storing these in a Git repository risks credential exposure. A secure storage strategy (e.g., secrets management tool, dedicated sealed namespace) must be defined before migration plans are authored at scale — otherwise plans either get stored insecurely or cannot be version-controlled.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 54: Windows VM Post-Migration Strategy

- **Issue**: MTV migrates Windows VMs but does not automatically install the QEMU guest agent (required for guest OS metrics, heartbeat, and graceful shutdown) or verify that VirtIO drivers are functioning correctly. VMware Tools must be removed to avoid conflicts. Manual post-migration remediation for a large Windows VM fleet is not scalable — a standardized, automated post-migration playbook (e.g., Ansible via AAP) is required to ensure consistency and auditability across migration waves.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 55: Guest OS Lifecycle Management (In-Guest Patching)

- **Issue**: Enterprise patching tools (WSUS, SCCM, Satellite) and EDR/security agents communicate over the network and are expected to operate unchanged after hypervisor migration, provided VMs retain their VLAN connectivity. However, any tools with VMware-specific dependencies (e.g., VMware Tools hooks) may be affected. Sandbox validation of the full patching and security scan cycle on migrated VMs must be completed before production migration waves to avoid discovering compatibility issues at scale.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 56: Post-Migration Validation Framework

- **Issue**: Without a standardized post-migration validation checklist, VMs may be declared healthy before application-level issues surface. The checklist should cover: QEMU guest agent status, VirtIO driver verification, network connectivity (ping, DNS, application port), application health checks, and storage performance baseline. Source VMware VMs should remain powered off (not deleted) for a defined holdback period to enable rollback. A clear sign-off process with defined owners (platform team vs. application owner) must be established before waves begin.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 57: Migration Workload Triage and Wave Planning

- **Issue**: Not all VMs should be migrated — EOL OS versions should be rebuilt, appliances with no KVM/OCP-V vendor support should be evaluated for replacement, and unused VMs should be decommissioned. A scoring or triage model must define these criteria before waves are planned. Wave composition must account for inter-VM dependencies (migrate application groups together), application criticality tier (start low-criticality to build confidence), hardware dependencies (USB passthrough, PCI devices, physical CD-ROM), and available migration bandwidth and change management capacity.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 58: MTV Controller Placement and Migration Network

- **Issue**: The MTV forklift-controller runs on the destination OCP-V cluster. Migration data flows from vCenter/ESXi via VDDK through an MTV pod to the CSI/CDI storage backend. A dedicated migration network (10Gbps minimum recommended) is needed to prevent migration traffic from impacting production VM workloads during large migration waves. Concurrent migration limits must be tuned to avoid saturating storage or network bandwidth. VDDK must be hosted as a container image (enterprise registry or equivalent) accessible from the destination cluster. MTV controller placement (masters vs. workers) affects resource competition during peak migration activity.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 59: OpenShift Virtualization Operator Baseline (HCO / CDI / VM Workload Updates)

- **Issue**: HyperConverged Cluster Operator settings (default storage class for VMs, CDI upload/import behavior, workload update strategy, feature gates, VNC TLS) span multiple day-2 concerns; without a single baseline, GitOps drift and upgrade behavior become inconsistent across the fleet. A standard HCO spec fragment per cluster class should be defined and checked into GitOps. Key sub-decisions include workload update strategy (coordinate with ADR 47), default storage classes for VM disks (align with ADR 18), feature gates such as hotplug (align with ADR 20), and VNC/console exposure (align with ADR 33). The baseline must be validated in sandbox on the target OCP version before production rollout.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 60: VM Golden Images, Boot Sources, and DataSources

- **Issue**: OCP-V relies on boot sources and golden images for new VM provisioning. Ownership, registry paths, update cadence, and content trust (image signing) must be defined. A central catalog of approved images (RHEL, Windows sources, appliances) should be maintained in an accessible registry. VirtIO-win distribution method (internal mirror vs. bundled workflow) must be decided. Cloning and import permissions should follow least privilege aligned with the RBAC model (ADR 29). Without a defined catalog, teams may import ad-hoc images that complicate security scanning and create unsupported combinations.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 61: CPU / NUMA / Dedicated Resources for Performance-Sensitive VMs

- **Issue**: Architecture discussions include CPU pinning, NUMA topology awareness, dedicated CPUs, and huge pages for latency-sensitive workloads. Without an instance-type catalog (ADR 37), exceptions for performance-sensitive VMs must still be governed. Dedicated CPUs and huge pages may conflict with LiveMigrate (ADR 38) — exceptions must state migration expectations. A default of no dedicated CPUs or huge pages keeps the fleet simple; an exception process requiring capacity/architecture review and security sign-off ensures targeted performance tuning where justified.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 62: SR-IOV, GPU, and PCI Passthrough Policy

- **Issue**: PCI passthrough (SR-IOV, GPU, USB) changes migration, scheduling, and security posture. VMs with passthrough devices cannot live migrate — conflicting with the LiveMigrate-first eviction strategy (ADR 38). The RBAC model must control device assignment. Dedicated clusters or node pools may be required for passthrough-heavy workloads to avoid scheduling conflicts with the standard migratable estate. A default of no GPU/SR-IOV/passthrough for standard migrated VMs, with an architecture exception process for justified cases, keeps the bulk of the fleet on the standard model.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 63: Guest NIC Name Preservation Strategy During Migration

- **Issue**: VMware to OCP-V migration can alter guest Linux interface names when the underlying driver changes (e.g., `ens192` to `enp1s0`). Workloads with static network configuration tied to interface names can lose connectivity post-migration. Determine whether fleet-wide NIC name preservation is required, or whether a workload-exception model is sufficient. Options include virt-v2v interface name persistence, udev rules in a pre-migration guest remediation step, or accepting the default behavior and relying on post-migration validation to surface affected workloads.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 64: MTV Migration Hooks vs AAP-Orchestrated Remediation

- **Issue**: MTV provides native pre- and post-migration hooks that execute in-workflow automation (e.g., guest remediation, validation scripts) tightly coupled to the VM cutover event. External AAP orchestration offers richer retry logic, ITSM integration, and clearer ownership separation but adds coordination complexity. For large migration waves, the boundary between hook-driven and AAP-driven automation must be defined to prevent conflicting remediation paths and audit gaps.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---

### ADR 65: Partial Wave Failure Handling Policy

- **Issue**: Large migration waves are unlikely to complete with 100% VM success. Without a formal policy, wave closure decisions become ad-hoc and may delay subsequent waves or leave the environment in a mixed state. Define: success threshold (100% required or controlled partial completion), retry policy for failed VMs (same window, next window, or rollback trigger), when the holdback clock starts for a partially successful wave, and the sign-off required before failed VMs are formally deferred.
- **Decision**: 
- **Status**: 
- **Assumptions**: 
- **Argument**: 

---
