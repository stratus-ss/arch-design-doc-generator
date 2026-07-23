"""Generic sanitization replacement rules for draw.io diagram scrubbing.

This public version intentionally contains no client-specific patterns.
Use these examples as a starter set, then add your own patterns for each
engagement before publishing artifacts.
"""

REPLACEMENTS = [
    # Organization and environment naming
    (r"\bExampleCorp\b", "{ORG_NAME}"),
    (r"\bexamplecorp\b", "{ORG_SLUG}"),
    (r"\bProd\b", "{ENV_PROD}"),
    (r"\bNon-Prod\b", "{ENV_NONPROD}"),
    # Site and tier naming
    (r"\bPrimary DC\b", "Tier 1 Site"),
    (r"\bDR Site\b", "Tier 2 Site"),
    (r"\bBranch\b", "Tier 3 Site"),
    # Hostnames and domains
    (r"\b[a-z0-9.-]+\.examplecorp\.com\b", "{HOST_FQDN}"),
    (r"\bgithub\.examplecorp\.com\b", "{GITOPS_HOST}"),
    # Capacity and count examples
    (r"~\d+\s+clusters", "N clusters"),
    (r"~\d+\s+sites", "N sites"),
    # Vendor normalization examples
    (r"\bVendorA\b", "{BACKUP_VENDOR}"),
    (r"\bVendorB\b", "{SIEM_VENDOR}"),
]
