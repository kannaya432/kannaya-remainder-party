"""Vercel serverless entrypoint for FastAPI."""

import sys
from pathlib import Path

# Ensure src/ is on sys.path for the planner package.
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from planner.app import create_app  # noqa: E402

app = create_app()
