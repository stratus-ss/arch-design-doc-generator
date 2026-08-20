#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_SHARED_LIB = _SCRIPT_DIR.parent / "shared" / "lib"
for extra_path in (_SHARED_LIB, _SCRIPT_DIR):
    extra = str(extra_path)
    if extra not in sys.path:
        sys.path.insert(0, extra)

from hc_report.link_review.cli import main

if __name__ == "__main__":
    main()
