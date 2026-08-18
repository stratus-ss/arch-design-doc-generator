from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def pythonpath_setup(project_root: Path) -> None:
    lib_path = str(project_root / "scripts" / "shared" / "lib")
    if lib_path in sys.path:
        sys.path.remove(lib_path)
    sys.path.insert(0, lib_path)
