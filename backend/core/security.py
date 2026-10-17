"""Who may call which route: the portfolio's admin (Firebase ID token of the /admin sign-in) or the Vercel Cron job."""

import secrets

from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from backend.core.config import setting

_google = google_requests.Request()


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


def require_cron(authorization: str | None = Header(default=None)) -> None:
    """Vercel Cron sends "Authorization: Bearer <CRON_SECRET>" (vercel.json schedules the call)."""
    if not secrets.compare_digest(authorization or "", f"Bearer {setting('CRON_SECRET')}"):
        raise HTTPException(401, "Not the scheduled job")
