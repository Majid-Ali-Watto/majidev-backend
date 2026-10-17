"""Only the portfolio's admin may call the API: requests carry the Firebase ID token of the /admin sign-in."""

import os

from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

_google = google_requests.Request()


def setting(name: str) -> str:
    """A required environment variable (see README.md)."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise HTTPException(500, f"{name} is not set on the server")
    return value


def require_admin(authorization: str | None = Header(default=None)) -> str:
    """Verifies the bearer token against Google's Firebase signing keys and returns the admin's uid."""
    project = setting("FIREBASE_PROJECT_ID")
    admin_uid = setting("ADMIN_UID")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Sign in to /admin first")
    try:
        claims = id_token.verify_firebase_token(token, _google, audience=project, clock_skew_in_seconds=10)
    except ValueError as err:  # bad signature, expired, wrong audience, malformed
        raise HTTPException(401, "Your sign-in is invalid or expired; sign in again") from err
    if claims.get("iss") != f"https://securetoken.google.com/{project}" or claims.get("sub") != admin_uid:
        raise HTTPException(403, "This account is not the portfolio admin")
    return admin_uid
