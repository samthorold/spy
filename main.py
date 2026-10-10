"""Entry point: `uv run uvicorn main:app`. The app itself lives in the `app` package."""

from app.web import app

__all__ = ["app"]
