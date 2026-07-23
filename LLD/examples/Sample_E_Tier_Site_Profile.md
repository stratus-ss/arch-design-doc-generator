# Low-Level Design — Sample E: Tier-Based Site Profile

> **FORMAT SAMPLE** — This document demonstrates the Tier-Based Site Profile LLD format using Phase 1 (Foundation) content from the Acme Corp HLD. It is not a production LLD.

---

## About This Format

| Attribute | Description |
|-----------|-------------|
| **Style** | Organized by deployment tier — each tier section is a self-contained, complete specification |
| **Audience** | Tier-owning teams who need the full picture for "their" environment without cross-referencing other tiers |
| **Strength** | A DC engineer reads only the DC profile; a branch tech reads only the Branch profile — no filtering needed |
| **Navigation** | Jump directly to the relevant tier; use the Tier Comparison Summary for quick deltas |
| **Relationship to HLD** | Repackages all HLD Phase 1 decisions through a per-tier lens instead of per-component |

---

## Document Control

| Field | Value |
|---|---|
| **Title** | Acme Corp OpenShift Virtualization — Phase 1 Foundation LLD (Tier-Based Site Profile) |
| **Version** | 0.1 |
| **Status** | Draft |
| **Classification** | Internal — Confidential |
| **Author** | {AUTHOR} |
| **Reviewers** | {REVIEWER_LIST} |
| **Approval Authority** | {APPROVER} |
| **Last Updated** | {DATE} |

### Revision History

| Ver | Date | Author | Changes |
|-----|------|--------|---------|
| 0.1 | {DATE} | {AUTHOR} | Initial tier-based site profiles — Phase 1 Foundation |

---

## Scope

This LLD provides a complete Phase 1 (Foundation) specification for each of the three Acme Corp deployment tiers. Each tier profile is self-contained — a reader working on Datacenter deployments can use the DC profile without referencing CDF or Branch content.

### References

| Document | Location |
|----------|----------|
| Acme Corp HLD — Phase 1 Foundation | `HLD/markdown_files/Acme Corp_OCP-V_HLD_DecisionJourney_phase1.md` |
| Acme Corp HLD — Cross-Cutting | `HLD/markdown_files/Acme Corp_OCP-V_HLD_CrossCutting.md` |

---

## Tier Comparison Summary

Quick-reference delta table — consult individual tier profiles for full detail.

| Domain | Datacenter | CDF | Branch |
|--------|-----------|-----|--------|
| **Sites** | Site Alpha, Site Beta | Regional CDFs | ~400 branch locations |
| **Nodes** | 3 CP + 16+ workers | 3 CP + variable workers | 3 compact (CP + worker + ODF) |
| **Hardware** | Cisco UCS M8 | Cisco UCS M8 | Cisco Unified Edge |
| **vNICs** | 4 (full bond separation) | 4 (baseline) | 2 (TBD, combined bonds) |
| **Storage** | IBM FlashSystem FC SAN | IBM FlashSystem FC SAN | ODF local NVMe (replica 3) |
| **Network layers** | Mgmt, VM, Storage, Migration, Backup, FC, BMC | Mgmt, VM, Storage, Migration, Backup, FC, BMC | Mgmt, VM, Backup, BMC |
| **MTU (non-mgmt)** | 9000/9216 | 9000/9216 | 9000 (backup only) |
| **ACM Hub** | DC/CDF hub | DC/CDF hub | Branch hub |
| **LB** | keepalived/haproxy | keepalived/haproxy | keepalived/haproxy |
| **maxUnavailable** | 2-4 | 1-2 | 1 |
| **HA reserve** | ~10% (1-3 spare nodes) | 10-20% | 34% (N-1 of 3) |
| **Egress model** | Firewall-only (no proxy) | Firewall-only (no proxy) | TBD |
| **FC SAN zoning** | Required | Required | N/A |

---

## Datacenter Tier Profile

### DC-1: Tier Overview

| Field | Value |
|---|---|
| **Tier** | Datacenter |
| **Sites** | Site Alpha, Site Beta |
| **ACM Hub** | DC/CDF hub |
| **Node topology** | 3 control plane (schedulable) + 16+ workers |
| **Hardware** | Cisco UCS M8 managed via Intersight |
| **OCP version** | 4.21 (stable channel) |
| **Pods-per-node** | 512 |
| **Pod subnet** | 192.168.0.0/17 (hostPrefix /22) |
| **Service subnet** | 192.168.128.0/18 |

### DC-2: Hardware & Server Profiles

**Intersight server profile policies:**

| Policy | Value |
|--------|-------|
| BIOS | Cisco "virtualization" preset — VT-x, VT-d, NX bit enabled |
| Boot | UEFI; local disk or SAN boot |
| vNIC 0 | FI-A, management VLAN, MTU 1500 |
| vNIC 1 | FI-B, all VM VLANs, MTU 1500 |
| vNIC 2 | Dedicated, migration VLAN, MTU 9000 |
| vNIC 3 | Dedicated, backup VLAN, MTU 9000 |
| PCI Placement | Enabled (ADR 7) |
| IPMI | Disabled at Day 0; hardened post-install |

**Day-0 MachineConfig:**

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  labels:
    machineconfiguration.openshift.io/role: worker
  name: 99-worker-kernel-psi
spec:
  kernelArguments:
    - psi=1
```

### DC-3: Network Specification

**Network layers:**

| Layer | VLAN | MTU | Purpose |
|-------|------|-----|---------|
| Management | Site-specific | 1500 | OCP API, etcd, DNS, NTP, node-to-node |
| VM Data | Multiple (all presented) | 1500 | VM tenant traffic via OVS bridges + NADs |
| Storage | Site-specific | 9000/9216 | FlashSystem FC block access |
| Migration | Dedicated | 9000 | Live migration memory page transfer |
| Backup | Dedicated | 9000 | {BACKUP_VENDOR} agent backup traffic |
| FC SAN | FC zoning | N/A | FlashSystem block access |
| BMC/CIMC | Site-specific | 1500 | Out-of-band management, Redfish |

**IP allocation per cluster:**

| IP Type | Count | Network |
|---------|-------|---------|
| API VIP | 1 | Baremetal (management) |
| Ingress VIP | 1 | Baremetal (management) |
| Control plane IPs | 3 | Baremetal |
| Worker IPs | 16+ | Baremetal |
| BMC IPs | 1 per node (~19+) | BMC VLAN |
| Storage IPs | 1 per node | Storage VLAN |
| Migration IPs | 1 per node | Migration VLAN |
| Backup IPs | 1 per node | Backup VLAN |

**Load balancer:** Built-in keepalived/haproxy (ADR 12). F5 is DNS-path only (GTM).

### DC-4: DNS Records

| Record Type | FQDN | Target |
|-------------|------|--------|
| A + PTR | `api.<cluster>.<base_domain>` | API VIP |
| A + PTR | `api-int.<cluster>.<base_domain>` | API VIP |
| Wildcard A | `*.apps.<cluster>.<base_domain>` | Ingress VIP |
| A + PTR | `<hostname>.<cluster>.<base_domain>` per node | Node IP |

Provider: Infoblox. PTR records required — RHCOS uses them to set hostnames.

### DC-5: NTP

| Parameter | Value |
|---|---|
| NTP servers | DC internal NTP (SRE-managed) |
| Delivery | chrony MachineConfig via ArgoCD; ACM inform policy monitors compliance |
| Max offset | < 100ms |
| Guest VM time | No hypervisor sync — Windows via AD, Linux via NTP directly |

### DC-6: Certificates

| Certificate | Subject / SAN | Issuer | Timing |
|-------------|--------------|--------|--------|
| API server | `api.<cluster>.<base_domain>` | Enterprise CA | Day 0 |
| Ingress wildcard | `*.apps.<cluster>.<base_domain>` | Internal CA | Day 0 |

Post-install: create TLS secret in `openshift-ingress`, patch IngressController. cert-manager automates rotation.

### DC-7: Firewall Rules

Egress model: Firewall-only (no proxy, ADR 16). VM traffic bypasses cluster egress via bridged VLANs.

| Rule Group | Ports | Protocol | Purpose |
|------------|-------|----------|---------|
| Inter-node (all <-> all) | ICMP, 1936, 9000-9999, 10250-10259, 22623, 6081, 30000-32767 | TCP/UDP/ICMP | Cluster internal |
| All → CP | 6443 | TCP | Kubernetes API |
| CP <-> CP | 2379-2380 | TCP | etcd |
| LB → CP | 6443, 22623 | TCP | API + MCS via LB |
| LB → Workers | 80, 443 | TCP | Ingress |
| ACM hub <-> Cluster | 443, 6443 | TCP | Hub management |
| ACM hub → BMC | 443 | TCP | Redfish |
| BMC → Hub | 6180, 6183 | TCP | Virtual media ISO |
| Hub <-> Nodes (Ironic) | 5050, 6385, 9999 | TCP | Provisioning |
| Nodes → External | 123/UDP, 443/TCP, 53/TCP+UDP | Mixed | NTP, Artifactory, DNS |

**Additional DC-specific:** FC SAN ports between nodes and FlashSystem (site-specific).

### DC-8: Capacity

| Parameter | Value |
|---|---|
| Target CPU utilization | 60-70% |
| Memory overcommit | Disabled |
| Headroom | 1-3 spare worker nodes |
| maxUnavailable | 2-4 |
| Pods-per-node | 512 |

### DC-9: Provisioning

Method: ACM ZTP via Assisted Installer. SiteConfig CR applied to DC/CDF ACM hub.

```yaml
platform:
  baremetal:
    apiVIPs:
      - <api_vip>
    ingressVIPs:
      - <ingress_vip>
networking:
  clusterNetwork:
    - cidr: 192.168.0.0/17
      hostPrefix: 22
  serviceNetwork:
    - 192.168.128.0/18
  networkType: OVNKubernetes
```

Registry: Artifactory pull-through cache. In-cluster registry: ephemeral mode.

### DC-10: Pre-Flight Validation

| Check | Command | Pass Criteria |
|-------|---------|---------------|
| DNS — API | `dig api.<cluster>.<base_domain>` | API VIP |
| DNS — Wildcard | `dig test.apps.<cluster>.<base_domain>` | Ingress VIP |
| DNS — Node A + PTR | `dig` / `dig -x` per node | Correct IP / FQDN |
| NTP | `chronyc sources` | Synced, offset < 100ms |
| BMC | `curl -sk https://<bmc_ip>/redfish/v1/Systems` | HTTP 200 |
| NIC cabling | Intersight inventory | All 4 vNICs present |
| IP conflict | `arping -D -c 3 <ip>` per IP + VIP | No duplicate |
| FW — API | `nc -zv <api_vip> 6443` | Succeeds |
| FW — etcd | `nc -zv <cp_ip> 2379` from peer | Succeeds |
| Certificates | `openssl x509 -noout -dates` | Valid, SAN matches |
| Pull secret | `podman login <artifactory>` | Succeeds |
| Disk perf | `fio` sequential write | p99 fsync < 10ms |
| **FC SAN path** | `multipath -ll` or FC switch verification | Paths visible |

### DC-11: Gate 1 Criteria

- [ ] Cluster API reachable from management network
- [ ] etcd quorum healthy (3 members)
- [ ] All 16+ worker nodes joined and Ready
- [ ] Console accessible via ingress
- [ ] Enterprise TLS certificates active (API + Ingress)
- [ ] NTP synced on all nodes
- [ ] FC SAN paths visible from worker nodes

---

## CDF Tier Profile

### CDF-1: Tier Overview

| Field | Value |
|---|---|
| **Tier** | CDF / Regional |
| **Sites** | Regional CDF locations |
| **ACM Hub** | DC/CDF hub |
| **Node topology** | 3 control plane (schedulable) + variable workers |
| **Hardware** | Cisco UCS M8 managed via Intersight |
| **OCP version** | 4.21 (stable channel) |

### CDF-2: Hardware & Server Profiles

Identical to DC profile (4 vNICs, same Intersight policies, PCI placement enabled). Same Day-0 PSI MachineConfig.

### CDF-3: Network Specification

Same layers as DC. Key differences:

| Parameter | CDF-Specific |
|---|---|
| VLAN IDs | Site-specific (differ from DC) |
| Worker count | Variable — smaller than DC |
| Object storage | ICOS (or WAN to nearest DC) |

### CDF-4: DNS, NTP, Certificates

Identical patterns to DC — site-specific NTP servers, same Infoblox DNS record structure, same certificate issuers.

### CDF-5: Firewall Rules

Same rule set as DC, including FC SAN ports. Egress: firewall-only.

### CDF-6: Capacity

| Parameter | Value |
|---|---|
| Headroom | 10-20% |
| maxUnavailable | 1-2 |

All other capacity parameters match DC.

### CDF-7: Gate 1 Criteria

Same as DC Gate 1, with worker count adjusted to site-specific topology.

---

## Branch Tier Profile

### BR-1: Tier Overview

| Field | Value |
|---|---|
| **Tier** | Branch (3-node compact on Cisco Unified Edge) |
| **Sites** | ~400 branch locations |
| **ACM Hub** | Branch hub |
| **Node topology** | 3 compact nodes (CP + worker + ODF on each) |
| **Hardware** | Cisco Unified Edge |
| **OCP version** | 4.21 (stable channel) |

### BR-2: Hardware & Server Profiles

| Policy | Branch-Specific |
|--------|----------------|
| vNIC count | 2 (TBD — combined bonds) |
| Storage | Local NVMe (ODF) — no FC SAN |
| PCI Placement | Enabled (ADR 7) |
| Server profile | Unified Edge template |

**Key difference from DC/CDF:** No dedicated storage or migration vNICs. Traffic combines onto 2 vNICs with bond separation TBD.

### BR-3: Network Specification

| Layer | VLAN | MTU | Purpose |
|-------|------|-----|---------|
| Management | Site-specific | 1500 | OCP API, etcd, DNS, NTP |
| VM Data | Site-specific | 1500 | VM tenant traffic |
| Backup | Dedicated | 9000 | {BACKUP_VENDOR} agent backup (WAN to DC) |
| BMC/CIMC | Site-specific | 1500 | Out-of-band management |

**Not applicable at Branch:** Storage VLAN, Migration VLAN, FC SAN zoning.

**IP allocation per cluster:**

| IP Type | Count |
|---------|-------|
| API VIP | 1 |
| Ingress VIP | 1 |
| Compact node IPs | 3 (baremetal) |
| BMC IPs | 3 |
| Backup IPs | 3 |

**Total: ~11 IPs per branch cluster** (vs ~50+ for DC).

### BR-4: DNS Records

Same record types as DC (API, API-int, wildcard, per-node A+PTR) — 3 node records instead of 19+.

### BR-5: NTP

| Parameter | Value |
|---|---|
| NTP servers | Branch network NTP (TBD — unconfirmed) |
| Delivery | chrony MachineConfig via ArgoCD |

**Open item:** Branch NTP server confirmation required.

### BR-6: Certificates

Same as DC — API cert from Enterprise CA, Ingress wildcard from Internal CA. Per-cluster wildcard exception (ADR 24).

### BR-7: Firewall Rules

Same inter-node and external rules as DC. Key differences:

| Difference | Detail |
|---|---|
| Egress model | TBD (DC/CDF confirmed firewall-only) |
| FC SAN rules | Not applicable |
| Ironic ports | Required (ACM ZTP) |

### BR-8: Capacity

| Parameter | Value |
|---|---|
| Headroom | 34% (N-1 of 3 nodes) |
| maxUnavailable | 1 |
| Storage | ODF local NVMe, replica 3, ~1.6 TB total |
| ODF overhead | 10-15% of resources |

No capacity concerns currently anticipated for branch workloads.

### BR-9: Provisioning

Method: ACM ZTP via Branch hub + GitOps ZTP pipeline with SiteConfig CRs for at-scale deployment.

```yaml
platform:
  baremetal:
    apiVIPs:
      - <api_vip>
    ingressVIPs:
      - <ingress_vip>
    hosts:
      - name: node-0
        role: master
        bmc:
          address: redfish-virtualmedia://<bmc_ip>/redfish/v1/Systems/1
      - name: node-1
        role: master
        bmc:
          address: redfish-virtualmedia://<bmc_ip>/redfish/v1/Systems/1
      - name: node-2
        role: master
        bmc:
          address: redfish-virtualmedia://<bmc_ip>/redfish/v1/Systems/1
```

All 3 nodes are `master` role in compact topology.

### BR-10: Pre-Flight Validation

Same checklist as DC, with these differences:

| Check | Branch-Specific |
|---|---|
| NIC cabling | 2 vNICs expected (not 4) |
| FC SAN path | Not applicable |
| BMC count | 3 nodes only |
| Node count | 3 compact nodes |

### BR-11: Gate 1 Criteria

- [ ] Cluster API reachable
- [ ] etcd quorum healthy (3 members)
- [ ] All 3 compact nodes joined and Ready
- [ ] Console accessible via ingress
- [ ] Enterprise TLS certificates active
- [ ] NTP synced on all nodes
- [ ] ODF health confirmed (3 OSDs healthy)

---

## Common Configuration (All Tiers)

Parameters that are identical across DC, CDF, and Branch — maintained here to avoid duplication.

| Parameter | Value | Source |
|-----------|-------|--------|
| OCP version | 4.21 | HLD — OCP Version Strategy |
| Update channel | stable | HLD — OCP Version Strategy |
| Pod subnet | 192.168.0.0/17 | HLD — Cluster Network CIDRs |
| Service subnet | 192.168.128.0/18 | HLD — Cluster Network CIDRs |
| Host CIDR prefix | /22 | HLD — Cluster Network CIDRs |
| Pods-per-node | 512 | HLD — Capacity & Headroom |
| Memory overcommit | Disabled | HLD — Capacity |
| Target CPU utilization | 60-70% | HLD — Capacity |
| LB model | keepalived/haproxy (built-in) | ADR 12 |
| Registry | Artifactory pull-through cache | ADR 4 |
| In-cluster registry | Ephemeral mode | HLD — Container Image Registry |
| API cert issuer | Enterprise CA | ADR 24 |
| Ingress cert issuer | Internal CA | ADR 24 |
| cert-manager | Automates rotation post-install | HLD — TLS Certificates |
| DNS provider | Infoblox | HLD — DNS Prerequisites |
| Provisioning | ACM ZTP (all tiers) | HLD — Provisioning Method |
| BIOS profile | Cisco "virtualization" preset | CVD baseline |
| PCI placement | Enabled | ADR 7 |

---

## Open Items by Tier

| ID | Tier | Item | Owner | Status |
|----|------|------|-------|--------|
| OI-E-01 | Branch | 2-vNIC layout finalization | Network Team | Open |
| OI-E-02 | Branch | Egress model decision | Network / Architecture | Open |
| OI-E-03 | Branch | NTP server confirmation | Network Team | Open |
| OI-E-04 | Branch | Bandwidth / local Artifactory mirror | Network Team | Open |
| OI-E-05 | All | BIOS validation against OCP requirements | Platform / Red Hat | Open |
| OI-E-06 | All | IPMI post-install hardening procedure | Platform / Cisco | Open |
| OI-E-07 | All | BIOS time propagation (Intersight NTP vs BIOS) | BC Team / Cisco | Open |
