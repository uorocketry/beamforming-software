"""Make the `beamcontrol` package importable from tests whether or not it is installed.

Runs both under `uv run pytest` (package installed editable) and a bare
`python -m pytest pi` (src dir on sys.path).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
