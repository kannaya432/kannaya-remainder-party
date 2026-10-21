"""Entry point: ``python -m planner``."""

import os

import uvicorn

from planner.app import create_app


def main() -> None:
    """Runs the server on ``$PORT`` (default 8080)."""
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(create_app(), host="0.0.0.0", port=port)  # noqa: S104


if __name__ == "__main__":
    main()
