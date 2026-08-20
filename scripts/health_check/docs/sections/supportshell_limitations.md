| Capability | Live (`collect/`) | Offline (`supportshell/`) |
|-----------|-------------------|--------------------------|
| Resource listings (`oc get`) | ✓ | ✓ (via `omc`) |
| Text-format captures (`oc get -o wide`) | ✓ | ✓ |
| `oc exec` into pods (etcdctl, prometheus curl) | ✓ | ✗ |
| `oc adm top nodes/pods` | ✓ | ✗ |
| `oc debug node` (DMI/BIOS data) | ✓ | Partial (extracted from `sysinfo.tgz` in must-gather — vendor, product, BIOS, CPU, memory available; disk rotational detection unavailable) |
| Live firing alerts | ✓ | ✗ |

Checks that depend on unavailable data are marked `SKIPPED` or `NOT_APPLICABLE` in the report.
