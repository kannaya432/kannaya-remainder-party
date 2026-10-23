"""Vercel serverless entrypoint for FastAPI."""

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# Search candidates so sys.path resolves across runtime environments
_HERE = Path(__file__).resolve().parent
for candidate in [
    _HERE.parent / "src",
    _HERE / "src",
    _HERE.parent,
    Path.cwd() / "src",
    Path.cwd(),
    Path("/var/task/src"),
    Path("/var/task"),
]:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

try:
    from planner.app import create_app

    app = create_app()
except Exception as exc:
    log.exception("Failed to initialize FastAPI application: %s", exc)
    raise
