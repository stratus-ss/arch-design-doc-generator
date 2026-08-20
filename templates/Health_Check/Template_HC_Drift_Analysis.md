# OpenShift Architecture Decision Record — Drift Analysis

**Customer:** {CLIENT}  
**Cluster:** {CLUSTER_NAME}  
**OCP Version:** {OCP_VERSION}  
**Health Check Date:** {REPORT_DATE}  
**ADR Reference:** {ADR_SOURCE}  
**Report Date:** {DRIFT_REPORT_DATE}  
**Author:** {AUTHOR}  

---

> **About this document:** This Drift Analysis compares the architecture decisions documented in the customer's Architecture Decision Record (ADR) against the actual cluster state observed during the OpenShift Health Check. Each ADR decision is evaluated as **MATCH** (cluster state consistent with decision), **DRIFT** (cluster state deviates from decision), or **UNKNOWN** (insufficient data to determine). This report highlights where implementation has diverged from intended architecture and provides prioritized recommendations for realignment.
>
> **Status: not implemented.** This template describes an aspirational ADR-vs-cluster drift classifier. No automated generator (`parse_report.py`, `generate_drift.py`, or equivalent) currently exists in this repository, and no Makefile target produces this document. The health-check pipeline (`make hc-collect` / `make hc-report`) does not consume ADR data. Use this template only as a manually authored deliverable, or treat it as a future-work placeholder.

---

## Executive Summary

{EXECUTIVE_SUMMARY}

### Overall Drift Assessment

| Status | Count |
|--------|-------|
| MATCH  | {MATCH_COUNT} |
| DRIFT  | {DRIFT_COUNT} |
| UNKNOWN | {UNKNOWN_COUNT} |
| **Total ADRs Evaluated** | {TOTAL_ADR_COUNT} |

**Overall Health:** {OVERALL_HEALTH}

---

## Methodology

Each ADR decision was compared against findings from the OpenShift Health Check report using the following process:

1. **Deterministic mapping:** ADR decision categories (Installation, Network, Storage, Security, Migration) were mapped to Health Check Chapter 7 categories (Base Platform, Components, Storage, Security, etc.)
2. **AI-assisted analysis:** For each mapped pair, an AI classifier determined MATCH/DRIFT/UNKNOWN status by comparing the ADR's stated decision with the observed cluster configuration
3. **Impact assessment:** For each DRIFT, an impact narrative was generated describing operational and support risk
4. **Remediation guidance:** Actionable steps to realign the cluster with the original architectural intent were provided

**Status Definitions:**

| Status | Meaning |
|--------|---------|
| MATCH | Cluster state is consistent with the ADR decision |
| DRIFT | Cluster state deviates materially from the ADR decision |
| UNKNOWN | Insufficient data collected during health check to make a determination |

---

## Drift Analysis

{DRIFT_ANALYSIS_SECTIONS}

---

## Summary Statistics

### Drift by ADR Category

| ADR Category | MATCH | DRIFT | UNKNOWN | Total |
|-------------|-------|-------|---------|-------|
{CATEGORY_STATS_ROWS}

### Top Priority Remediations

{TOP_PRIORITY_REMEDIATIONS}

---

## Recommendations

### Immediate Actions (P0 Drifts)

{IMMEDIATE_ACTIONS}

### Short-Term Remediations (P1–P2 Drifts)

{SHORT_TERM_REMEDIATIONS}

### Long-Term Architecture Alignment

{LONG_TERM_ALIGNMENT}

---

## Appendix: ADR Decision Reference

The following ADR decisions were evaluated in this analysis. Full ADR text available in the source ADR document.

{ADR_REFERENCE_TABLE}

---

*This drift analysis is a point-in-time assessment based on the health check data collected on {REPORT_DATE}. Cluster state changes after the data collection date are not reflected.*
