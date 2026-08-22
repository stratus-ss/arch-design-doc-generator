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

## Section 1: Filled Example — {TIER_PRIMARY} Tier Cluster

### 1.1 Cluster Identity

*HLD Reference: Phase 1 — Deployment Tier Model*

| Field | Value |
|---|---|
| **Cluster Name** | `{CLUSTER_NAME}` |
| **Base Domain** | `<base_domain>` |
| **Full API FQDN** | `api.<cluster>.<base_domain>` |
| **Full Ingress FQDN** | `*.apps.<cluster>.<base_domain>` |
| **Tier** | Datacenter |
| **Site** | `{SITE_1}` |
| **ACM Hub** | ACM {TIER_PRIMARY}/{TIER_MIDDLE} Hub |
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
| Control Plane | cp-0 | `<serial>` | `<cluster>-cp` | `<bmc_ip>` | `<bmc_mac>` | `<boot_mac>` |
| Control Plane | cp-1 | `<serial>` | `<cluster>-cp` | `<bmc_ip>` | `<bmc_mac>` | `<boot_mac>` |
| Control Plane | cp-2 | `<serial>` | `<cluster>-cp` | `<bmc_ip>` | `<bmc_mac>` | `<boot_mac>` |
| Worker | worker-0 | `<serial>` | `<cluster>-wk` | `<bmc_ip>` | `<bmc_mac>` | `<boot_mac>` |
| Worker | worker-1 | `<serial>` | `<cluster>-wk` | `<bmc_ip>` | `<bmc_mac>` | `<boot_mac>` |
| ... | ... | ... | ... | ... | ... | ... |
| Worker | worker-N | `<serial>` | `<cluster>-wk` | `<bmc_ip>` | `<bmc_mac>` | `<boot_mac>` |

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
| Management | 100 | `<mgmt_subnet>` | `<mgmt_gateway>` | 1500 |
| VM Data | 200-210 | Various | Various | 1500 |
| Storage | 300 | `<storage_subnet>` | `<storage_gateway>` | 9000 |
| Migration | 400 | `<migration_subnet>` | `<migration_gateway>` | 9000 |
| Backup | 500 | `<backup_subnet>` | `<backup_gateway>` | 9000 |
| BMC | 600 | `<bmc_subnet>` | `<bmc_gateway>` | 1500 |

**VIPs:**

| VIP Type | IP Address | Network | VLAN | Infoblox Reserved |
|----------|-----------|---------|------|-------------------|
| API VIP | `<api_vip>` | Management | 100 | [x] |
| Ingress VIP | `<ingress_vip>` | Management | 100 | [x] |

**Per-Node IP Assignments:**

| Hostname | Mgmt IP | Storage IP | Migration IP | Backup IP | BMC IP |
|----------|---------|------------|-------------|-----------|--------|
| cp-0 | `<mgmt_ip>` | `<storage_ip>` | `<migration_ip>` | `<backup_ip>` | `<bmc_ip>` |
| cp-1 | `<mgmt_ip>` | `<storage_ip>` | `<migration_ip>` | `<backup_ip>` | `<bmc_ip>` |
| cp-2 | `<mgmt_ip>` | `<storage_ip>` | `<migration_ip>` | `<backup_ip>` | `<bmc_ip>` |
| worker-0 | `<mgmt_ip>` | `<storage_ip>` | `<migration_ip>` | `<backup_ip>` | `<bmc_ip>` |
| worker-1 | `<mgmt_ip>` | `<storage_ip>` | `<migration_ip>` | `<backup_ip>` | `<bmc_ip>` |
| ... | ... | ... | ... | ... | ... |
| worker-N | `<mgmt_ip>` | `<storage_ip>` | `<migration_ip>` | `<backup_ip>` | `<bmc_ip>` |

### 1.4 DNS Records

*HLD Reference: Phase 1 — DNS, Static IPs & NTP Prerequisites*

| Record Type | FQDN | Target | Created | Verified |
|-------------|------|--------|---------|----------|
| A + PTR | `api.<cluster>.<base_domain>` | `<api_vip>` | [x] | [x] |
| A + PTR | `api-int.<cluster>.<base_domain>` | `<api_vip>` | [x] | [x] |
| Wildcard A | `*.apps.<cluster>.<base_domain>` | `<ingress_vip>` | [x] | [x] |
| A + PTR | `<hostname>.<cluster>.<base_domain>` | `<node_ip>` | [x] | [x] |
| A + PTR | `<hostname>.<cluster>.<base_domain>` | `<node_ip>` | [x] | [x] |
| A + PTR | `<hostname>.<cluster>.<base_domain>` | `<node_ip>` | [x] | [x] |
| A + PTR | `<hostname>.<cluster>.<base_domain>` | `<node_ip>` | [x] | [x] |
| ... | ... | ... | ... | ... |
| A + PTR | `<hostname>.<cluster>.<base_domain>` | `<node_ip>` | [x] | [x] |

### 1.5 Certificate Inventory

*HLD Reference: Phase 1 — TLS/SSL Certificates; ADR 24*

| Certificate | Subject / SAN | Issued By | Expiry | Received | Validated |
|-------------|--------------|-----------|--------|----------|-----------|
| API server | `api.<cluster>.<base_domain>` | Enterprise CA | `<expiry_date>` | [x] | [x] |
| Ingress wildcard | `*.apps.<cluster>.<base_domain>` | Internal CA | `<expiry_date>` | [x] | [x] |

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
| NTP Server 1 | `ntp1.<base_domain>` |
| NTP Server 2 | `ntp2.<base_domain>` |
| MachineConfig applied | [x] |
| All nodes synced | [x] |
| Max offset observed | 12ms |

### 1.8 Pre-Flight Validation

*HLD Reference: Phase 1 — Pre-Flight Validation Checklist*

| # | Check | Result | Pass/Fail |
|---|-------|--------|-----------|
| 1 | DNS — API resolves to `<api_vip>` | `<api_vip>` | Pass |
| 2 | DNS — API-int resolves to `<api_vip>` | `<api_vip>` | Pass |
| 3 | DNS — Wildcard resolves to `<ingress_vip>` | `<ingress_vip>` | Pass |
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

## Section 2: Filled Example — {TIER_EDGE} Tier Cluster (3-Node Compact)

### 2.1 Cluster Identity

| Field | Value |
|---|---|
| **Cluster Name** | `{CLUSTER_NAME}` |
| **Base Domain** | `<base_domain>` |
| **Full API FQDN** | `api.<cluster>.<base_domain>` |
| **Full Ingress FQDN** | `*.apps.<cluster>.<base_domain>` |
| **Tier** | {TIER_EDGE} (3-node compact) |
| **Site** | {SITE} {TIER_EDGE} |
| **ACM Hub** | ACM {TIER_EDGE} Hub |
| **OCP Version** | 4.21 |
| **Node Count** | 3 compact (CP + Worker + ODF) |

### 2.2 Hardware Assignment

| Node Role | Hostname | Serial Number | Intersight Profile | BMC IP | Boot MAC |
|-----------|----------|---------------|-------------------|--------|----------|
| Compact | node-0 | `<serial>` | `<cluster>` | `<bmc_ip>` | `<boot_mac>` |
| Compact | node-1 | `<serial>` | `<cluster>` | `<bmc_ip>` | `<boot_mac>` |
| Compact | node-2 | `<serial>` | `<cluster>` | `<bmc_ip>` | `<boot_mac>` |

### 2.3 Network Allocation

**VLANs:**

| Network Layer | VLAN ID | Subnet | Gateway | MTU |
|---------------|---------|--------|---------|-----|
| Management | 100 | `<mgmt_subnet>` | `<mgmt_gateway>` | 1500 |
| VM Data | 200-202 | Various | Various | 1500 |
| Backup | 500 | `<backup_subnet>` | `<backup_gateway>` | 9000 |
| BMC | 600 | `<bmc_subnet>` | `<bmc_gateway>` | 1500 |

*No dedicated storage or migration VLANs — local ODF, combined bonds.*

**VIPs:**

| VIP Type | IP Address | Infoblox Reserved |
|----------|-----------|-------------------|
| API VIP | `<api_vip>` | [x] |
| Ingress VIP | `<ingress_vip>` | [x] |

**Per-Node IP Assignments:**

| Hostname | Mgmt IP | Backup IP | BMC IP |
|----------|---------|-----------|--------|
| node-0 | `<mgmt_ip>` | `<backup_ip>` | `<bmc_ip>` |
| node-1 | `<mgmt_ip>` | `<backup_ip>` | `<bmc_ip>` |
| node-2 | `<mgmt_ip>` | `<backup_ip>` | `<bmc_ip>` |

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
| **Tier** | [ ] Datacenter  [ ] {TIER_MIDDLE}  [ ] {TIER_EDGE} |
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
