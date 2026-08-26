"""Compatibility shim retained for frozen historical verifier imports."""
import sys
from pathlib import Path
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from backend.core.schema_fingerprint import *  # noqa: F401,F403
