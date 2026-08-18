#!/usr/bin/env python3
"""Stub `oc` for Health Check collection tests. No live cluster."""
from __future__ import annotations

import json
import sys


INFRA = {
    "kind": "Infrastructure",
    "apiVersion": "config.openshift.io/v1",
    "metadata": {"name": "cluster"},
    "spec": {"platformSpec": {"none": {}}},
    "status": {"infrastructureName": "test-cluster-abc123"},
}

CLUSTERVERSION = {
    "kind": "ClusterVersion",
    "apiVersion": "config.openshift.io/v1",
    "metadata": {"name": "version"},
    "spec": {"channel": "stable-4.18"},
    "status": {"desired": {"version": "4.18.1"}},
}

PLACEHOLDER_LIST = {
    "kind": "List",
    "apiVersion": "v1",
    "items": [{"kind": "PlaceHolder", "metadata": {"name": "fixture", "uid": "uid-1"}}],
}


def _resource_name(argv: list[str]) -> str:
    if "get" not in argv:
        return ""
    idx = argv.index("get") + 1
    while idx < len(argv):
        token = argv[idx]
        if token in ("-n", "-o", "-l", "--namespace", "--output"):
            idx += 2
            continue
        if token.startswith("-"):
            idx += 1
            continue
        return token
    return ""


def main() -> None:
    argv = sys.argv[1:]
    if "cluster-info" in argv:
        print("Kubernetes control plane is running at https://api.fixture.test:6443")
        return
    if "get" not in argv:
        print("unknown oc invocation", file=sys.stderr)
        sys.exit(1)
    resource = _resource_name(argv)
    payloads = {
        "infrastructure": INFRA,
        "clusterversion": CLUSTERVERSION,
    }
    json.dump(payloads.get(resource, PLACEHOLDER_LIST), sys.stdout)
    print()


if __name__ == "__main__":
    main()
