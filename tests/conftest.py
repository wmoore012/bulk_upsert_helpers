"""
Pytest configuration helpers.

Ensures the package's ``src`` directory is on ``sys.path`` so the tests can
import ``bulk_upsert_helpers`` without requiring an editable install first.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    """Add ``../src`` to ``sys.path`` when running the test suite."""
    project_root = Path(__file__).resolve().parents[1]
    src_path = project_root / "src"
    src_str = str(src_path)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


_ensure_src_on_path()
