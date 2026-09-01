# Design: native virt P3 leaves

Mint the nine natives listed in the delta spec. Keep StorageProfile and CNV quota as full TSR rows for `hc_native_virt_p3_remainder`. Do not alias IN leaves to `7.4.cnv.state`, `7.4.cnv.nncp`, `7.4.cnv.live_migratable`, or `7.4.cnv.pods`. Do not scrape PromQL for VMI phase; use `cnv_vmi` `.status.phase`.

Live `06_layered` MAY write `cnv_cdi` and `cnv_virt_handler_ds`. Supportshell MAY write the same names.

New evaluators live in `evaluators/layered_cnv.py`. `evaluate_layered` dispatches `evaluate_cnv_p3` only.

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
