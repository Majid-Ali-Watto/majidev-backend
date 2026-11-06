"""Who may call which route: the portfolio's admin (Firebase ID token of the /admin sign-in) or the Vercel Cron job."""

import re
import secrets
import threading
import time

from fastapi import Header, HTTPException
from google.auth.exceptions import TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from backend.core.config import setting
from backend.core.errors import UpstreamError

MAX_AGE = re.compile(r"max-age=(\d+)")


class _CachedGet:
    """A google-auth transport that keeps each successful GET until its Cache-Control max-age passes.

    google-auth downloads Google's signing keys on every verification; this reuses them for as long as Google allows,
    so a request (including one with a junk token) costs no outbound call while the keys are fresh.
    """

    def __init__(self, request: google_requests.Request):
        self._request = request
        self._cache: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def __call__(self, url, method="GET", **kwargs):
        if method != "GET":
            return self._request(url, method=method, **kwargs)
        with self._lock:
            expires, response = self._cache.get(url, (0.0, None))
            if time.monotonic() < expires:
                return response
            # Bounded: google-auth's default is 120 s, and this lock would hold every other verification behind a hung fetch
            kwargs.setdefault("timeout", 10)
            response = self._request(url, method=method, **kwargs)
            max_age = MAX_AGE.search(response.headers.get("cache-control", "")) if response.status == 200 else None
            if max_age:
                self._cache[url] = (time.monotonic() + int(max_age.group(1)), response)
            return response


_google = _CachedGet(google_requests.Request())


def require_admin(authorization: str | None = Header(default=None)) -> str:
    """Verifies the bearer token against Google's Firebase signing keys and returns the admin's uid."""
    project = setting("FIREBASE_PROJECT_ID")
    admin_uid = setting("ADMIN_UID")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Sign in to /admin first")
    try:
        claims = id_token.verify_firebase_token(token, _google, audience=project, clock_skew_in_seconds=10)
    except TransportError as err:  # Google's signing keys could not be fetched
        raise UpstreamError(f"Could not reach Google to verify the sign-in: {err}") from err
    except ValueError as err:  # bad signature, expired, wrong audience, malformed
        raise HTTPException(401, "Your sign-in is invalid or expired; sign in again") from err
    if claims.get("iss") != f"https://securetoken.google.com/{project}" or claims.get("sub") != admin_uid:
        raise HTTPException(403, "This account is not the portfolio admin")
    # Same rule as the site's firestore.rules: only a sign-in that used the authenticator app (TOTP second factor)
    if (claims.get("firebase") or {}).get("sign_in_second_factor") != "totp":
        raise HTTPException(403, "Sign in to /admin with your authenticator app code first")
    return admin_uid


def require_cron(authorization: str | None = Header(default=None)) -> None:
    """Vercel Cron sends "Authorization: Bearer <CRON_SECRET>" (vercel.json schedules the call)."""
    # Compared as bytes: compare_digest raises TypeError for non-ASCII str, which would answer 500 instead of 401
    expected = f"Bearer {setting('CRON_SECRET')}".encode()
    if not secrets.compare_digest((authorization or "").encode(), expected):
        raise HTTPException(401, "Not the scheduled job")
