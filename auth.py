"""Google / Microsoft sign-in (OpenID Connect id_token) and signed session cookies.

Standard library only, so it runs unchanged locally and on Vercel.

Environment:
  GOOGLE_CLIENT_ID      OAuth client ID (Google Cloud Console → Credentials → Web application)
  MICROSOFT_CLIENT_ID   Application (client) ID (Azure → App registrations), ID tokens enabled
  SESSION_SECRET        Random string used to sign the session cookie (required on Vercel)
Sign-in is switched off when neither client ID is set.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import ssl
import time
import urllib.request

SESSION_COOKIE = "tj_session"
SESSION_TTL = 12 * 3600

JWKS_URLS = {
    "google": "https://www.googleapis.com/oauth2/v3/certs",
    "microsoft": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
}
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
MICROSOFT_ISSUER = re.compile(r"^https://login\.microsoftonline\.com/[0-9a-f-]{36}/v2\.0$")

# DER prefix of a SHA-256 DigestInfo (RSASSA-PKCS1-v1_5)
_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
_jwks_cache: dict[str, tuple[float, dict]] = {}
_fallback_secret = secrets.token_hex(32)


def client_ids() -> dict:
    return {
        "google": os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        "microsoft": os.environ.get("MICROSOFT_CLIENT_ID", "").strip(),
    }


def auth_enabled() -> bool:
    return any(client_ids().values())


def _secret() -> bytes:
    s = os.environ.get("SESSION_SECRET")
    if not s and auth_enabled() and os.environ.get("VERCEL"):
        print("[auth] SESSION_SECRET is not set; sessions will not survive between serverless instances", flush=True)
    return (s or _fallback_secret).encode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _ssl_context() -> ssl.SSLContext:
    paths = ssl.get_default_verify_paths()
    if not (paths.cafile or (paths.capath and os.path.isdir(paths.capath) and os.listdir(paths.capath))) \
            and os.path.exists("/etc/ssl/cert.pem"):
        return ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    return ssl.create_default_context()


def _jwks(provider: str, refresh: bool = False) -> dict:
    cached = _jwks_cache.get(provider)
    if cached and not refresh and time.time() - cached[0] < 3600:
        return cached[1]
    req = urllib.request.Request(JWKS_URLS[provider], headers={"User-Agent": "TripjackCertificationV3/1.0"})
    with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as res:
        keys = {k["kid"]: k for k in json.load(res).get("keys", []) if k.get("kty") == "RSA"}
    _jwks_cache[provider] = (time.time(), keys)
    return keys


def _rs256_ok(jwk: dict, signed: bytes, sig: bytes) -> bool:
    n = int.from_bytes(_b64d(jwk["n"]), "big")
    e = int.from_bytes(_b64d(jwk["e"]), "big")
    k = (n.bit_length() + 7) // 8
    if len(sig) != k:
        return False
    em = pow(int.from_bytes(sig, "big"), e, n).to_bytes(k, "big")
    t = _SHA256_PREFIX + hashlib.sha256(signed).digest()
    expected = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return hmac.compare_digest(em, expected)


def verify_id_token(provider: str, token: str, nonce: str) -> dict:
    """Return {email, name, provider} for a valid id_token, else raise ValueError."""
    client_id = client_ids().get(provider)
    if not client_id:
        raise ValueError(f"{provider} sign-in is not configured")
    try:
        h64, p64, s64 = token.split(".")
        header, claims = json.loads(_b64d(h64)), json.loads(_b64d(p64))
    except Exception:
        raise ValueError("malformed token") from None
    if header.get("alg") != "RS256":
        raise ValueError("unexpected token algorithm")
    keys = _jwks(provider)
    if header.get("kid") not in keys:
        keys = _jwks(provider, refresh=True)  # keys rotate
    jwk = keys.get(header.get("kid"))
    if not jwk or not _rs256_ok(jwk, f"{h64}.{p64}".encode(), _b64d(s64)):
        raise ValueError("bad token signature")

    now = time.time()
    aud = claims.get("aud")
    if client_id != aud and not (isinstance(aud, list) and client_id in aud):
        raise ValueError("token is for another app")
    if claims.get("exp", 0) < now - 60 or claims.get("iat", now) > now + 300:
        raise ValueError("token expired")
    if not nonce or claims.get("nonce") != nonce:
        raise ValueError("nonce mismatch")
    iss = claims.get("iss", "")
    if provider == "google":
        if iss not in GOOGLE_ISSUERS:
            raise ValueError("unexpected issuer")
        if claims.get("email_verified") is False:
            raise ValueError("Google email is not verified")
        email = claims.get("email", "")
    else:
        if not MICROSOFT_ISSUER.match(iss) or claims.get("tid", "") not in iss:
            raise ValueError("unexpected issuer")
        email = claims.get("email") or claims.get("preferred_username") or ""
    if "@" not in email:
        raise ValueError("the account has no email address")
    return {"email": email.lower(), "name": claims.get("name") or email.split("@")[0], "provider": provider}


def make_session(user: dict) -> str:
    payload = _b64e(json.dumps({**user, "exp": int(time.time()) + SESSION_TTL}).encode())
    sig = _b64e(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_session(cookie_header: str | None) -> dict | None:
    for part in (cookie_header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name != SESSION_COOKIE or "." not in value:
            continue
        payload, sig = value.rsplit(".", 1)
        good = _b64e(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        try:
            data = json.loads(_b64d(payload))
        except Exception:
            return None
        return data if data.get("exp", 0) > time.time() else None
    return None


def session_cookie(value: str, secure: bool, max_age: int = SESSION_TTL) -> str:
    return (f"{SESSION_COOKIE}={value}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax"
            + ("; Secure" if secure else ""))
