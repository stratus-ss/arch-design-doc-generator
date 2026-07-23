# Low-Level Design — Sample C: Per-Cluster Build Sheet

> **FORMAT SAMPLE** — This document demonstrates the Per-Cluster Build Sheet LLD format using Phase 1 (Foundation) content from the Acme Corp HLD. It is not a production LLD.

---

## About This Format

| Attribute | Description |
|-----------|-------------|
| **Style** | Tabular fill-in-the-blanks worksheet organized around a single cluster deployment |
| **Audience** | Build engineers, site leads, project managers tracking deployment progress |
| **Strength** | Operational — directly usable as a deployment tracking artifact; one sheet per cluster |
| **Navigation** | Fill top to bottom; sign off at the end |
| **Relationship to HLD** | Tables map to HLD Phase 1 decisions; each section header references the source HLD section |
| **Usage** | Duplicate the blank template (Section 3) for each new cluster; fill in site-specific values |

---

## Document Control

| Field | Value |
|---|---|
| **Title** | Acme Corp OpenShift Virtualization — Phase 1 Foundation LLD (Build Sheet) |
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
| 0.1 | {DATE} | {AUTHOR} | Initial build sheet template and example — Phase 1 Foundation |

---

## How to Use This Sheet

1. **Copy Section 3** (blank template) for each cluster deployment
2. **Fill in all fields** as values are determined — the sheet tracks progress from planning through Gate 1
3. **Use the status columns** (checkboxes, Pass/Fail) to track completion
4. **Archive the completed sheet** as a deployment record after Gate 1 sign-off
5. Field names reference HLD Phase 1 sections — consult the HLD for decision rationale

---

## Section 1: Filled Example — DC Tier Cluster

### 1.1 Cluster Identity

*HLD Reference: Phase 1 — Deployment Tier Model*

| Field | Value |
|---|---|
| **Cluster Name** | ocp-sa-prod-01 |
| **Base Domain** | ocp.example.corp |
| **Full API FQDN** | api.ocp-sa-prod-01.ocp.example.corp |
| **Full Ingress FQDN** | *.apps.ocp-sa-prod-01.ocp.example.corp |
| **Tier** | Datacenter |
| **Site** | Site Alpha |
| **ACM Hub** | ACM DC/CDF Hub |
| **OCP Version** | 4.21 |
| **Update Channel** | stable |
| **Pod Subnet** | 192.168.0.0/17 |
| **Service Subnet** | 192.168.128.0/18 |
| **Host CIDR** | /22 |
| **Pods-per-Node** | 512 |
| **Node Count** | 3 CP + 16 workers = 19 total |

### 1.2 Hardware Assignment

*HLD Reference: Phase 1 — Hardware Provisioning & Network Fabric*

| Node Role | Hostname | Serial Number | Intersight Profile | BMC IP | BMC MAC | Boot MAC (vNIC 0) |
|-----------|----------|---------------|-------------------|--------|---------|-------------------|
| Control Plane | cp-0 | FCH2345A001 | ocp-sa-prod-01-cp | 10.1.100.10 | AA:BB:CC:00:01:00 | AA:BB:CC:01:01:00 |
| Control Plane | cp-1 | FCH2345A002 | ocp-sa-prod-01-cp | 10.1.100.11 | AA:BB:CC:00:01:01 | AA:BB:CC:01:01:01 |
| Control Plane | cp-2 | FCH2345A003 | ocp-sa-prod-01-cp | 10.1.100.12 | AA:BB:CC:00:01:02 | AA:BB:CC:01:01:02 |
| Worker | worker-0 | FCH2345A004 | ocp-sa-prod-01-wk | 10.1.100.13 | AA:BB:CC:00:01:03 | AA:BB:CC:01:01:03 |
| Worker | worker-1 | FCH2345A005 | ocp-sa-prod-01-wk | 10.1.100.14 | AA:BB:CC:00:01:04 | AA:BB:CC:01:01:04 |
| ... | ... | ... | ... | ... | ... | ... |
| Worker | worker-15 | FCH2345A019 | ocp-sa-prod-01-wk | 10.1.100.28 | AA:BB:CC:00:01:18 | AA:BB:CC:01:01:18 |

**Intersight Profile Status:**

| Check | Status |
|---|---|
| BIOS: virtualization preset applied | [x] |
| PCI placement rules enabled | [x] |
| vNIC count: 4 per node | [x] |
| IPMI: disabled (Day 0) | [x] |

### 1.3 Network Allocation

*HLD Reference: Phase 1 — IP Reservations & Load Balancer VIPs; Hardware Provisioning & Network Fabric*

**VLANs:**

| Network Layer | VLAN ID | Subnet | Gateway | MTU |
|---------------|---------|--------|---------|-----|
| Management | 100 | 10.1.1.0/24 | 10.1.1.1 | 1500 |
| VM Data | 200-210 | Various | Various | 1500 |
| Storage | 300 | 10.1.3.0/24 | 10.1.3.1 | 9000 |
| Migration | 400 | 10.1.4.0/24 | 10.1.4.1 | 9000 |
| Backup | 500 | 10.1.5.0/24 | 10.1.5.1 | 9000 |
| BMC | 600 | 10.1.100.0/24 | 10.1.100.1 | 1500 |

**VIPs:**

| VIP Type | IP Address | Network | VLAN | Infoblox Reserved |
|----------|-----------|---------|------|-------------------|
| API VIP | 10.1.1.200 | Management | 100 | [x] |
| Ingress VIP | 10.1.1.201 | Management | 100 | [x] |

**Per-Node IP Assignments:**

| Hostname | Mgmt IP | Storage IP | Migration IP | Backup IP | BMC IP |
|----------|---------|------------|-------------|-----------|--------|
| cp-0 | 10.1.1.10 | 10.1.3.10 | 10.1.4.10 | 10.1.5.10 | 10.1.100.10 |
| cp-1 | 10.1.1.11 | 10.1.3.11 | 10.1.4.11 | 10.1.5.11 | 10.1.100.11 |
| cp-2 | 10.1.1.12 | 10.1.3.12 | 10.1.4.12 | 10.1.5.12 | 10.1.100.12 |
| worker-0 | 10.1.1.20 | 10.1.3.20 | 10.1.4.20 | 10.1.5.20 | 10.1.100.13 |
| worker-1 | 10.1.1.21 | 10.1.3.21 | 10.1.4.21 | 10.1.5.21 | 10.1.100.14 |
| ... | ... | ... | ... | ... | ... |
| worker-15 | 10.1.1.35 | 10.1.3.35 | 10.1.4.35 | 10.1.5.35 | 10.1.100.28 |

### 1.4 DNS Records

*HLD Reference: Phase 1 — DNS, Static IPs & NTP Prerequisites*

| Record Type | FQDN | Target | Created | Verified |
|-------------|------|--------|---------|----------|
| A + PTR | api.ocp-sa-prod-01.ocp.example.corp | 10.1.1.200 | [x] | [x] |
| A + PTR | api-int.ocp-sa-prod-01.ocp.example.corp | 10.1.1.200 | [x] | [x] |
| Wildcard A | *.apps.ocp-sa-prod-01.ocp.example.corp | 10.1.1.201 | [x] | [x] |
| A + PTR | cp-0.ocp-sa-prod-01.ocp.example.corp | 10.1.1.10 | [x] | [x] |
| A + PTR | cp-1.ocp-sa-prod-01.ocp.example.corp | 10.1.1.11 | [x] | [x] |
| A + PTR | cp-2.ocp-sa-prod-01.ocp.example.corp | 10.1.1.12 | [x] | [x] |
| A + PTR | worker-0.ocp-sa-prod-01.ocp.example.corp | 10.1.1.20 | [x] | [x] |
| ... | ... | ... | ... | ... |
| A + PTR | worker-15.ocp-sa-prod-01.ocp.example.corp | 10.1.1.35 | [x] | [x] |

### 1.5 Certificate Inventory

*HLD Reference: Phase 1 — TLS/SSL Certificates; ADR 24*

| Certificate | Subject / SAN | Issued By | Expiry | Received | Validated |
|-------------|--------------|-----------|--------|----------|-----------|
| API server | api.ocp-sa-prod-01.ocp.example.corp | Enterprise CA | 2028-04-01 | [x] | [x] |
| Ingress wildcard | *.apps.ocp-sa-prod-01.ocp.example.corp | Internal CA | 2028-04-01 | [x] | [x] |

### 1.6 Firewall Rule Checklist

*HLD Reference: Phase 1 — Firewall Rules & Port Requirements; ADR 16*

| Rule ID | Traffic Path | Ports | Change Request # | Implemented | Verified |
|---------|-------------|-------|-----------------|-------------|----------|
| FW-01 | Inter-node (all <-> all) | ICMP | CHG-12345 | [x] | [x] |
| FW-02 | Inter-node | 1936/TCP | CHG-12345 | [x] | [x] |
| FW-03 | Inter-node | 9000-9999/TCP+UDP | CHG-12345 | [x] | [x] |
| FW-04 | Inter-node | 10250-10259/TCP | CHG-12345 | [x] | [x] |
| FW-05 | Inter-node | 22623/TCP | CHG-12345 | [x] | [x] |
| FW-06 | Inter-node | 6081/UDP | CHG-12345 | [x] | [x] |
| FW-07 | Inter-node | 30000-32767/TCP+UDP | CHG-12345 | [x] | [x] |
| FW-08 | All → CP | 6443/TCP | CHG-12345 | [x] | [x] |
| FW-09 | CP <-> CP | 2379-2380/TCP | CHG-12345 | [x] | [x] |
| FW-10 | LB → CP | 6443, 22623/TCP | CHG-12345 | [x] | [x] |
| FW-11 | LB → Workers | 80, 443/TCP | CHG-12345 | [x] | [x] |
| FW-12 | ACM Hub <-> Cluster | 443, 6443/TCP | CHG-12346 | [x] | [x] |
| FW-13 | ACM Hub → BMC | 443/TCP | CHG-12346 | [x] | [x] |
| FW-14 | BMC → Hub | 6180, 6183/TCP | CHG-12346 | [x] | [x] |
| FW-15 | Hub <-> Nodes (Ironic) | 5050, 6385, 9999/TCP | CHG-12346 | [x] | [x] |
| FW-16 | Nodes → NTP | 123/UDP | CHG-12347 | [x] | [x] |
| FW-17 | Nodes → Artifactory | 443/TCP | CHG-12347 | [x] | [x] |
| FW-18 | Nodes → DNS | 53/TCP+UDP | CHG-12347 | [x] | [x] |

### 1.7 NTP Configuration

*HLD Reference: Phase 1 — DNS, Static IPs & NTP Prerequisites*

| Parameter | Value |
|---|---|
| NTP Server 1 | ntp1.ash.example.corp |
| NTP Server 2 | ntp2.ash.example.corp |
| MachineConfig applied | [x] |
| All nodes synced | [x] |
| Max offset observed | 12ms |

### 1.8 Pre-Flight Validation

*HLD Reference: Phase 1 — Pre-Flight Validation Checklist*

| # | Check | Result | Pass/Fail |
|---|-------|--------|-----------|
| 1 | DNS — API resolves to 10.1.1.200 | 10.1.1.200 | Pass |
| 2 | DNS — API-int resolves to 10.1.1.200 | 10.1.1.200 | Pass |
| 3 | DNS — Wildcard resolves to 10.1.1.201 | 10.1.1.201 | Pass |
| 4 | DNS — All node A records correct | All match | Pass |
| 5 | DNS — All node PTR records correct | All match | Pass |
| 6 | NTP — Synced, offset < 100ms | 12ms | Pass |
| 7 | BMC — All 19 nodes reachable via Redfish | HTTP 200 (19/19) | Pass |
| 8 | NIC — Cabling verified via Intersight | All present | Pass |
| 9 | IP — No conflicts (arping all IPs + VIPs) | No duplicates | Pass |
| 10 | FW — API port 6443 open | Connected | Pass |
| 11 | FW — Ingress port 443 open | Connected | Pass |
| 12 | FW — etcd port 2379 open (peer) | Connected | Pass |
| 13 | Certs — Valid, SAN matches, not expired | Valid | Pass |
| 14 | Pull secret — Artifactory login succeeds | Login OK | Pass |
| 15 | Disk — fio p99 fsync < 10ms | 4.2ms | Pass |

**Pre-flight result: ALL PASS — proceed to installation**

### 1.9 Installation & Gate 1

| Milestone | Timestamp | Status |
|-----------|-----------|--------|
| SiteConfig CR applied | 2026-05-10 09:00 | Complete |
| All agents discovered | 2026-05-10 09:15 | Complete |
| Installation started | 2026-05-10 09:20 | Complete |
| Installation completed | 2026-05-10 10:35 | Complete |
| Post-install certs applied | 2026-05-10 10:50 | Complete |
| NTP MachineConfig applied | 2026-05-10 11:05 | Complete |
| Gate 1 validation passed | 2026-05-10 11:30 | **PASSED** |

### 1.10 Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Build Engineer | | | |
| Platform Lead | | | |
| Network Lead | | | |
| Security Lead | | | |
| Project Manager | | | |

---

## Section 2: Filled Example — Branch Tier Cluster (3-Node Compact)

### 2.1 Cluster Identity

| Field | Value |
|---|---|
| **Cluster Name** | ocp-sd-fairview-01 |
| **Base Domain** | ocp.example.corp |
| **Full API FQDN** | api.ocp-sd-fairview-01.ocp.example.corp |
| **Full Ingress FQDN** | *.apps.ocp-sd-fairview-01.ocp.example.corp |
| **Tier** | Branch (3-node compact) |
| **Site** | Fairview Branch |
| **ACM Hub** | ACM Branch Hub |
| **OCP Version** | 4.21 |
| **Node Count** | 3 compact (CP + Worker + ODF) |

### 2.2 Hardware Assignment

| Node Role | Hostname | Serial Number | Intersight Profile | BMC IP | Boot MAC |
|-----------|----------|---------------|-------------------|--------|----------|
| Compact | node-0 | UE-R001-001 | ocp-sd-fairview-01 | 10.50.100.10 | AA:BB:CC:50:01:00 |
| Compact | node-1 | UE-R001-002 | ocp-sd-fairview-01 | 10.50.100.11 | AA:BB:CC:50:01:01 |
| Compact | node-2 | UE-R001-003 | ocp-sd-fairview-01 | 10.50.100.12 | AA:BB:CC:50:01:02 |

### 2.3 Network Allocation

**VLANs:**

| Network Layer | VLAN ID | Subnet | Gateway | MTU |
|---------------|---------|--------|---------|-----|
| Management | 100 | 10.50.1.0/24 | 10.50.1.1 | 1500 |
| VM Data | 200-202 | Various | Various | 1500 |
| Backup | 500 | 10.50.5.0/24 | 10.50.5.1 | 9000 |
| BMC | 600 | 10.50.100.0/24 | 10.50.100.1 | 1500 |

*No dedicated storage or migration VLANs — local ODF, combined bonds.*

**VIPs:**

| VIP Type | IP Address | Infoblox Reserved |
|----------|-----------|-------------------|
| API VIP | 10.50.1.200 | [x] |
| Ingress VIP | 10.50.1.201 | [x] |

**Per-Node IP Assignments:**

| Hostname | Mgmt IP | Backup IP | BMC IP |
|----------|---------|-----------|--------|
| node-0 | 10.50.1.10 | 10.50.5.10 | 10.50.100.10 |
| node-1 | 10.50.1.11 | 10.50.5.11 | 10.50.100.11 |
| node-2 | 10.50.1.12 | 10.50.5.12 | 10.50.100.12 |

### 2.4 Pre-Flight & Gate 1 (abbreviated)

| # | Check | Pass/Fail |
|---|-------|-----------|
| 1-5 | DNS — all records | Pass |
| 6 | NTP synced | Pass |
| 7 | BMC reachable (3/3) | Pass |
| 8-15 | Remaining checks | Pass |

**Pre-flight result: ALL PASS**

| Milestone | Status |
|-----------|--------|
| Installation completed | Complete |
| Gate 1 passed | **PASSED** |

### 2.5 Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Build Engineer | | | |
| Platform Lead | | | |

---

## Section 3: Blank Template — Copy for Each New Cluster

### 3.1 Cluster Identity

| Field | Value |
|---|---|
| **Cluster Name** | |
| **Base Domain** | |
| **Full API FQDN** | |
| **Full Ingress FQDN** | |
| **Tier** | [ ] Datacenter  [ ] CDF  [ ] Branch |
| **Site** | |
| **ACM Hub** | |
| **OCP Version** | |
| **Update Channel** | |
| **Pod Subnet** | 192.168.0.0/17 |
| **Service Subnet** | 192.168.128.0/18 |
| **Host CIDR** | /22 |
| **Pods-per-Node** | 512 |
| **Node Count** | |

### 3.2 Hardware Assignment

| Node Role | Hostname | Serial Number | Intersight Profile | BMC IP | BMC MAC | Boot MAC |
|-----------|----------|---------------|-------------------|--------|---------|----------|
| | | | | | | |
| | | | | | | |
| | | | | | | |

**Intersight Profile Status:**

| Check | Status |
|---|---|
| BIOS: virtualization preset applied | [ ] |
| PCI placement rules enabled | [ ] |
| vNIC count: __ per node | [ ] |
| IPMI: disabled (Day 0) | [ ] |

### 3.3 Network Allocation

**VLANs:**

| Network Layer | VLAN ID | Subnet | Gateway | MTU |
|---------------|---------|--------|---------|-----|
| Management | | | | 1500 |
| VM Data | | | | 1500 |
| Storage | | | | 9000 |
| Migration | | | | 9000 |
| Backup | | | | 9000 |
| BMC | | | | 1500 |

**VIPs:**

| VIP Type | IP Address | Network | VLAN | Infoblox Reserved |
|----------|-----------|---------|------|-------------------|
| API VIP | | | | [ ] |
| Ingress VIP | | | | [ ] |

**Per-Node IP Assignments:**

| Hostname | Mgmt IP | Storage IP | Migration IP | Backup IP | BMC IP |
|----------|---------|------------|-------------|-----------|--------|
| | | | | | |
| | | | | | |
| | | | | | |

### 3.4 DNS Records

| Record Type | FQDN | Target | Created | Verified |
|-------------|------|--------|---------|----------|
| A + PTR | api.____.____ | | [ ] | [ ] |
| A + PTR | api-int.____.____ | | [ ] | [ ] |
| Wildcard A | *.apps.____.____ | | [ ] | [ ] |
| A + PTR | (per node) | | [ ] | [ ] |

### 3.5 Certificate Inventory

| Certificate | Subject / SAN | Issued By | Expiry | Received | Validated |
|-------------|--------------|-----------|--------|----------|-----------|
| API server | | Enterprise CA | | [ ] | [ ] |
| Ingress wildcard | | Internal CA | | [ ] | [ ] |

### 3.6 Firewall Rule Checklist

| Rule ID | Traffic Path | Ports | Change Request # | Implemented | Verified |
|---------|-------------|-------|-----------------|-------------|----------|
| FW-01 | Inter-node | ICMP | | [ ] | [ ] |
| FW-02 | Inter-node | 1936/TCP | | [ ] | [ ] |
| FW-03 | Inter-node | 9000-9999 | | [ ] | [ ] |
| FW-04 | Inter-node | 10250-10259/TCP | | [ ] | [ ] |
| FW-05 | Inter-node | 22623/TCP | | [ ] | [ ] |
| FW-06 | Inter-node | 6081/UDP | | [ ] | [ ] |
| FW-07 | Inter-node | 30000-32767 | | [ ] | [ ] |
| FW-08 | All → CP | 6443/TCP | | [ ] | [ ] |
| FW-09 | CP <-> CP | 2379-2380/TCP | | [ ] | [ ] |
| FW-10 | LB → CP | 6443, 22623/TCP | | [ ] | [ ] |
| FW-11 | LB → Workers | 80, 443/TCP | | [ ] | [ ] |
| FW-12 | ACM Hub <-> Cluster | 443, 6443/TCP | | [ ] | [ ] |
| FW-13 | ACM Hub → BMC | 443/TCP | | [ ] | [ ] |
| FW-14 | BMC → Hub | 6180, 6183/TCP | | [ ] | [ ] |
| FW-15 | Hub <-> Nodes | 5050, 6385, 9999/TCP | | [ ] | [ ] |
| FW-16 | Nodes → NTP | 123/UDP | | [ ] | [ ] |
| FW-17 | Nodes → Artifactory | 443/TCP | | [ ] | [ ] |
| FW-18 | Nodes → DNS | 53/TCP+UDP | | [ ] | [ ] |

### 3.7 NTP Configuration

| Parameter | Value |
|---|---|
| NTP Server 1 | |
| NTP Server 2 | |
| MachineConfig applied | [ ] |
| All nodes synced | [ ] |
| Max offset observed | |

### 3.8 Pre-Flight Validation

| # | Check | Result | Pass/Fail |
|---|-------|--------|-----------|
| 1 | DNS — API resolves | | |
| 2 | DNS — API-int resolves | | |
| 3 | DNS — Wildcard resolves | | |
| 4 | DNS — All node A records | | |
| 5 | DNS — All node PTR records | | |
| 6 | NTP — Synced, offset < 100ms | | |
| 7 | BMC — All nodes reachable | | |
| 8 | NIC — Cabling verified | | |
| 9 | IP — No conflicts | | |
| 10 | FW — API port 6443 | | |
| 11 | FW — Ingress port 443 | | |
| 12 | FW — etcd port 2379 | | |
| 13 | Certs — Valid, SAN matches | | |
| 14 | Pull secret — Artifactory login | | |
| 15 | Disk — fio p99 fsync < 10ms | | |

**Pre-flight result: ________**

### 3.9 Installation & Gate 1

| Milestone | Timestamp | Status |
|-----------|-----------|--------|
| SiteConfig CR applied | | |
| All agents discovered | | |
| Installation started | | |
| Installation completed | | |
| Post-install certs applied | | |
| NTP MachineConfig applied | | |
| Gate 1 validation passed | | |

### 3.10 Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Build Engineer | | | |
| Platform Lead | | | |
| Network Lead | | | |
| Security Lead | | | |
| Project Manager | | | |
