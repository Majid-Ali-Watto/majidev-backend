"""Errors any layer may raise; `main.py` answers them as `{"detail": message}` with their status code.

Services and repositories raise these instead of FastAPI's HTTPException, so they stay independent of the web layer.
"""


class AppError(Exception):
    status_code = 500

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class ConfigError(AppError):
    """A required environment variable is missing (see README.md)."""

    status_code = 500


class UpstreamError(AppError):
    """GitHub could not be reached, or refused the call."""

    status_code = 502
