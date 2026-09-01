# Design: native orphan user NetworkPolicy prune

Collect `networkpolicy` in live and supportshell `08_day2.sh`. Mint `7.6.netpol.orphan`. Keep TSR check_id via a sparse alias only. Do not retune `7.6.prune.netpol`.

Empty or missing `matchLabels` without `matchExpressions` is not an orphan (default-deny-all-pods). `matchExpressions` without `matchLabels` skips that policy. Labeled selectors count pods in that namespace whose labels contain every key/value; Succeeded/Failed pods are omitted. Zero user-namespace policies is INFO.

Scoring matrix and alias target are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
