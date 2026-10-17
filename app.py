"""Vercel entrypoint: Vercel serves the `app` this file exports. The application lives in the `backend` package."""

from backend.main import app

__all__ = ["app"]
