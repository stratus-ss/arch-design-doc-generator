# Design: native virt CPU flags (vmx/svm labels)

Mint `7.4.cnv.cpu_virt_flag`. Read existing `03_base_platform` nodes JSON. Do not add collect. Do not retarget `7.4.tsr.4_8_1_3_2_node_cpu`. Do not `oc debug` or parse `/proc/cpuinfo`. Either vmx or svm equal to string `true` counts; both are not required.

Evaluator lives in `evaluators/layered_cnv.py` as `_evaluate_cnv_cpu_virt_flag`, dispatched from `evaluate_cnv_p3` after existing P3 checks.

Scoring matrix is in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
