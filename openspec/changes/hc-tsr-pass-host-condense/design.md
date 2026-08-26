# Design: TSR identical PASS-host condensation

`_extract_leaf_check` already strips HTML then clips Result text at 32_000
characters. Large clusters emit one host block per node (Chrony 1.5.7.2). The
WARNING/LIMITATION line is early; identical PASS workers fill the buffer.

After `_strip_html`, `_condense_identical_pass_hosts` walks `ROLE NODES:::`
groups. `{label}::>ALL NODES:` is emitted only when every host in that group
is PASS/INFO-only (two or more hosts). Mixed groups keep every hostname.
Groups that already contain `>ALL NODES:` are left alone.

Clip still runs afterward. CCX `_extract_ccx_check` is unchanged.
