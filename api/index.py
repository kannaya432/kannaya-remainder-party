"""Vercel serverless entrypoint for FastAPI."""

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# Add current directory and candidate paths to sys.path
_HERE = Path(__file__).resolve().parent
for p in [str(_HERE), str(_HERE.parent / "src"), str(Path.cwd() / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from planner.app import create_app

app = create_app()
