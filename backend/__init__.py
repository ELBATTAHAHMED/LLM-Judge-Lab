"""JudgeLab backend package.

The backend remains executable through the established ``main:app`` entrypoint
while domain packages are introduced incrementally.  Keeping this directory on
``sys.path`` preserves the stable flat-module CLI contract used by frozen
verification scripts.
"""
from __future__ import annotations

import sys
from pathlib import Path


_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
