"""Environment settings (README.md lists them). Read on use, so a missing one fails that request with a clear 500
instead of crashing the app at import."""

import os

from backend.core.errors import ConfigError


def setting(name: str) -> str:
    """A required environment variable."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set on the server")
    return value


def allowed_origins() -> list[str]:
    """Where /admin runs, e.g. "https://majidev.netlify.app,http://localhost:5173" (optional: none allows no browser)."""
    return [origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",") if origin.strip()]
