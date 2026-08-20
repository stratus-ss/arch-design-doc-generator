#!/usr/bin/env python3
"""
generate_report.py — Health Check Report Generator entry point.

Delegates all logic to the hc_report package.

Usage:
    python3 scripts/health_check/generate_report.py \
        --results-dir output/hc_collect \
        --output-dir  output/Health_Check_Report \
        [--config project.yaml] \
        [--exec-summary "Overall cluster health is..."] \
        [--dry-run]
"""
from hc_report import main

if __name__ == "__main__":
    main()
