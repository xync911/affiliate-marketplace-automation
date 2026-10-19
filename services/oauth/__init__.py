"""OAuth account-connection framework.

Replaces manual key entry with per-platform "login account" flows.
Supported platforms use the official OAuth / token flow where one
exists; platforms without OAuth expose their official manual method
instead (see `manual` flag) rather than forcing a fake login.

Security model:
- Personal passwords are never requested or stored.
- Only tokens issued by the platform are persisted.
- Tokens are encrypted at rest (Fernet, key in OAUTH_ENCRYPTION_KEY
  env or derived from an auto-generated key file in config/).
- Containers load tokens from config/ volumes; no secret is baked
  into images.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from utils.logger import logger

TOKENS_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "oauth_tokens.json"
TOKENS_FILE.parent.mkdir(exist_ok=True)

_lock = threading.Lock()


def _get_encryption_key() -> bytes:
    """Return a stable Fernet key. Env wins, else a generated file."""
    from cryptography.fernet import Fernet

    env_key = os.getenv("OAUTH_ENCRYPTION_KEY")
    if env_key:
        return env_key.encode()
    keyfile = TOKENS_FILE.parent / ".oauth_key"
    if keyfile.exists():
        return keyfile.read_bytes()
    key = Fernet.generate_key()
    keyfile.write_bytes(key)
    try:
        keyfile.chmod(0o600)
    except OSError:
        pass
    return key


def _fernet():
    from cryptography.fernet import Fernet

    return Fernet(_get_encryption_key())


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""


@dataclass
class Platform:
    """Describes one integratable platform."""

    key: str
    name: str
    # True when the platform supports a login/OAuth flow in this app.
    oauth: bool = True
    # Official method used when oauth is False (documented to user).
    manual_method: str = ""
    # OAuth endpoints (empty => manual or non-standard flow)
    authorize_url: str = ""
    token_url: str = ""
    scopes: str = ""
    # Extra params required by some providers
    authorize_params: Dict[str, str] = field(default_factory=dict)
    # Verification: call this endpoint with a token to prove it works.
    verify_url: str = ""
    verify_kind: str = ""  # "get_json" | "post_form" | "aws_lwa" | "token_refresh"
    refresh_kind: str = ""  # how refresh token is exchanged
    client_id_env: str = ""
    client_secret_env: str = ""
    redirect_uri: str = ""
    notes: str = ""

    @property
    def supports_account_login(self) -> bool:
        return self.oauth


# ---------------------------------------------------------------------------
# Platform registry — official flows only
# ---------------------------------------------------------------------------
PLATFORMS: Dict[str, Platform] = {
    "google_ads": Platform(
        key="google_ads",
        name="Google Ads",
        oauth=True,
        authorize_url="https://accounts.google.com/o/oauth2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes="https://www.googleapis.com/auth/adwords",
        authorize_params={"access_type": "offline", "prompt": "consent"},
        verify_url="https://googleads.googleapis.com/v26/customers",
        verify_kind="get_json",
        refresh_kind="google",
        client_id_env="GOOGLE_ADS_CLIENT_ID",
        client_secret_env="GOOGLE_ADS_CLIENT_SECRET",
        notes="Uses Google OAuth 2.0 with offline refresh tokens.",
    ),
    # NOTE: facebook, instagram, youtube, twitter, tiktok removed from OAuth.
    # Use browser-auth instead (Jalur A).
    "amazon": Platform(
        key="amazon",
        name="Amazon (LWA / SP-API)",
        oauth=True,
        authorize_url="https://www.amazon.com/sp-api/login",
        token_url="https://api.amazon.com/auth/o2/token",
        scopes="sellingpartnerapi::notifications",
        verify_url="https://api.amazon.com/auth/o2/token",
        verify_kind="aws_lwa",
        refresh_kind="lwa",
        client_id_env="AMAZON_LWA_CLIENT_ID",
        client_secret_env="AMAZON_LWA_CLIENT_SECRET",
        notes="Amazon uses Login with Amazon (LWA); not classic OAuth.",
    ),
    "wordpress": Platform(
        key="wordpress",
        name="WordPress",
        oauth=False,
        manual_method=(
            "WordPress.com uses an OAuth 1.0a flow that requires signing up for an "
            "App at https://developer.wordpress.com/apps and providing an App ID "
            "and App Secret. It is OAuth, but the legacy 1.0a handshake is not "
            "served as a modern authorization-code redirect in this app, so the "
            "official integration is to generate an App ID + Secret there and paste "
            "them into the WordPress fields, then obtain an access token via the "
            "developer.wordpress.com API. Self-hosted WordPress instead uses a "
            "Site URL + App Password (created in user profile settings)."
        ),
        notes="No supported modern OAuth redirect in this app; documented manual flow.",
    ),
    "medium": Platform(
        key="medium",
        name="Medium",
        oauth=False,
        manual_method=(
            "Medium's developer API authenticates with an Integration Token that you "
            "create in your Medium profile under 'Integration Settings'. There is no "
            "public OAuth 2.0 authorization endpoint, so the official method is to "
            "generate that token and paste it here."
        ),
        notes="Token-only platform; no OAuth flow.",
    ),
    "github": Platform(
        key="github",
        name="GitHub",
        oauth=True,
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        scopes="repo,public_repo",
        verify_url="https://api.github.com/user",
        verify_kind="get_json",
        refresh_kind="none",
        client_id_env="GITHUB_CLIENT_ID",
        client_secret_env="GITHUB_CLIENT_SECRET",
        notes="GitHub OAuth 2.0 for user login.",
    ),
    # Manual-only affiliate networks (no public OAuth)
    "clickbank": Platform(
        key="clickbank",
        name="ClickBank",
        oauth=False,
        manual_method="ClickBank has no public OAuth; it issues a per-account API Key generated in the ClickBank dashboard. Enter that API Key manually.",
    ),
    "shareasale": Platform(
        key="shareasale",
        name="ShareASale (now Awin)",
        oauth=False,
        manual_method=(
            "ShareASale's standalone API was retired in Oct 2025; it is now Awin. "
            "Awin authenticates the account via an OAuth2 Bearer token generated in "
            "the Awin Platform UI under the user icon -> API Credentials. Generate that "
            "token in your Awin account and store it here; it is the official method."
        ),
    ),
    "awin": Platform(
        key="awin",
        name="Awin",
        oauth=False,
        manual_method=(
            "Awin uses an account-scoped OAuth2 Bearer token created in the Awin "
            "Platform UI (user icon -> API Credentials). Enter it here."
        ),
    ),
    "commission_junction": Platform(
        key="commission_junction",
        name="CJ (Commission Junction)",
        oauth=False,
        manual_method="CJ has no public OAuth; it issues a Developer Key and Website ID from the CJ dashboard. Enter both manually.",
    ),
    "impact": Platform(
        key="impact",
        name="Impact Radius",
        oauth=False,
        manual_method="Impact has no public OAuth; it issues an Account SID and Auth Token from the Impact dashboard API section. Enter both manually.",
    ),
    "rakuten": Platform(
        key="rakuten",
        name="Rakuten Advertising",
        oauth=False,
        manual_method="Rakuten Advertising has no public OAuth; it issues an API Key from the Rakuten Advertiser dashboard. Enter it manually.",
    ),
    # Marketplace affiliates without OAuth
    "shopee": Platform(
        key="shopee",
        name="Shopee Affiliate",
        oauth=False,
        manual_method="Shopee Affiliate uses a Partner ID, Partner Key and Shop ID from the Shopee Affiliate Partner dashboard. No public OAuth.",
    ),
    "tokopedia": Platform(
        key="tokopedia",
        name="Tokopedia Affiliate",
        oauth=False,
        manual_method="Tokopedia Affiliate uses App ID / App Secret / Affiliate ID from the Tokopedia affiliate dashboard. No public OAuth.",
    ),
    "blibli": Platform(
        key="blibli",
        name="Blibli Affiliate",
        oauth=False,
        manual_method="Blibli Affiliate uses Client ID, Client Secret and Username from the Blibli partner dashboard. No public OAuth.",
    ),
    "lazada": Platform(
        key="lazada",
        name="Lazada Affiliate",
        oauth=False,
        manual_method="Lazada Affiliate uses App Key / App Secret / Access Token from the Lazada affiliate dashboard. No public OAuth.",
    ),
    "tiktokshop": Platform(
        key="tiktokshop",
        name="TikTok Shop Affiliate",
        oauth=False,
        manual_method="TikTok Shop Affiliate uses App Key / App Secret / Access Token / Shop ID from the TikTok Shop Partner Center. No public OAuth in this app.",
    ),
    "threads": Platform(
        key="threads",
        name="Threads",
        oauth=False,
        manual_method="Threads uses a Meta-family token (App ID / App Secret / Access Token). Reuse the Meta connection via facebook_ads instead of a separate manual token.",
    ),
    "blogger": Platform(
        key="blogger",
        name="Blogger",
        oauth=True,
        authorize_url="https://accounts.google.com/o/oauth2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes="https://www.googleapis.com/auth/blogger",
        verify_url="https://www.googleapis.com/blogger/v3/users/me",
        verify_kind="get_json",
        refresh_kind="google",
        client_id_env="BLOGGER_CLIENT_ID",
        client_secret_env="BLOGGER_CLIENT_SECRET",
        notes="Uses Google OAuth 2.0.",
    ),
    "ghost": Platform(
        key="ghost",
        name="Ghost",
        oauth=False,
        manual_method="Ghost uses an Admin API Key from your Ghost dashboard (Settings -> Integrations -> API Keys). No public OAuth.",
    ),
    "substack": Platform(
        key="substack",
        name="Substack",
        oauth=False,
        manual_method="Substack uses a Publication URL plus an API Key generated under your Substack publication settings. No public OAuth.",
    ),
}


# ---------------------------------------------------------------------------
# Token store (encrypted)
# ---------------------------------------------------------------------------
def _load_store() -> Dict[str, Any]:
    if TOKENS_FILE.exists():
        try:
            return json.loads(TOKENS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_store(store: Dict[str, Any]) -> None:
    TOKENS_FILE.write_text(json.dumps(store, indent=2))


def get_token(platform_key: str) -> Optional[Dict[str, Any]]:
    with _lock:
        store = _load_store()
        rec = store.get(platform_key)
        if not rec:
            return None
        # decrypt secrets on the way out
        out = dict(rec)
        for field_name in ("access_token", "refresh_token", "client_id", "client_secret"):
            raw = out.get(field_name, "")
            if raw:
                out[field_name] = decrypt_secret(raw)
        return out


def store_token(platform_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a token record, encrypting sensitive fields."""
    with _lock:
        store = _load_store()
        secrets_fields = ["access_token", "refresh_token"]
        rec = dict(payload)
        rec["platform"] = platform_key
        rec["connected_at"] = datetime.now(timezone.utc).isoformat()
        for f in secrets_fields:
            if rec.get(f):
                rec[f] = encrypt_secret(str(rec[f]))
        store[platform_key] = rec
        _save_store(store)
        # return a non-encrypted copy for status display
        safe = {k: v for k, v in rec.items() if k not in secrets_fields}
        safe["connected_at"] = rec.get("connected_at")
        return safe


def remove_token(platform_key: str) -> bool:
    with _lock:
        store = _load_store()
        if platform_key in store:
            del store[platform_key]
            _save_store(store)
            return True
        return False


# ---------------------------------------------------------------------------
# OAuth flow (used by /authorize -> /callback)
# ---------------------------------------------------------------------------
# pending state store: state -> {platform, ...}
_pending: Dict[str, Dict[str, Any]] = {}


def build_authorize_url(platform: Platform, redirect_uri: str) -> Dict[str, Any]:
    """Return {url, state, expires_in_s}. Caller shows the URL to the user."""
    state = secrets.token_urlsafe(24)
    client_id = os.getenv(platform.client_id_env, "").strip()
    if not client_id:
        return {"error": f"missing client_id env {platform.client_id_env}"}

    params = dict(platform.authorize_params)
    params.update({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
    })
    if platform.scopes:
        scope_key = "scope" if platform.key != "tiktok_ads" else "scope"
        params[scope_key] = platform.scopes
    url = f"{platform.authorize_url}?{urlencode(params)}"
    _pending[state] = {"platform": platform.key, "created": datetime.now(timezone.utc)}
    return {"url": url, "state": state, "expires_in_s": 600}


def exchange_code(platform: Platform, code: str, redirect_uri: str) -> Dict[str, Any]:
    """Exchange an authorization code for tokens using httpx."""
    client_id = os.getenv(platform.client_id_env, "")
    client_secret = os.getenv(platform.client_secret_env, "")
    if platform.refresh_kind == "aws_lwa":
        # LWA uses form fields
        data = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": _pending and "authorization_code",
        }
        resp = httpx.post(platform.token_url, data=data, timeout=20)
        resp.raise_for_status()
        tok = resp.json()
        refresh = tok.get("refresh_token", "")
        if refresh:
            # store the raw refresh token; access tokens are 1h
            store_token(platform.key, {
                "access_token": tok.get("access_token", ""),
                "refresh_token": refresh,
                "account": tok.get("account_id", ""),
            })
        return {"status": "connected", "platform": platform.key}

    params = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    resp = httpx.post(platform.token_url, data=params, timeout=20)
    if resp.status_code >= 400:
        return {"status": "failed", "error": f"token exchange HTTP {resp.status_code}: {resp.text[:300]}"}
    tok = resp.json()
    store_token(platform.key, {
        "access_token": tok.get("access_token", ""),
        "refresh_token": tok.get("refresh_token", ""),
        "expires_in": tok.get("expires_in", 0),
    })
    return {"status": "connected", "platform": platform.key}


def refresh_access_token(platform: Platform) -> Optional[str]:
    """Return a fresh access token if a refresh token is available."""
    rec = get_token(platform.key)
    if not rec:
        return None
    rt = rec.get("refresh_token", "")
    if not rt:
        return rec.get("access_token", "")
    client_id = os.getenv(platform.client_id_env, "")
    client_secret = os.getenv(platform.client_secret_env, "")
    kind = platform.refresh_kind
    if kind == "google":
        data = {
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        resp = httpx.post(platform.token_url, data=data, timeout=15)
        resp.raise_for_status()
        new_at = resp.json().get("access_token", "")
        store_token(platform.key, {"access_token": new_at, "refresh_token": rt})
        return new_at
    if kind == "lwa":
        data = {
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": platform.scopes or "sellingpartnerapi::notifications",
        }
        resp = httpx.post(platform.token_url, data=data, timeout=15)
        resp.raise_for_status()
        new_at = resp.json().get("access_token", "")
        store_token(platform.key, {"access_token": new_at, "refresh_token": rt})
        return new_at
    if kind == "meta":
        data = {
            "grant_type": "fb_exchange_token",
            "fb_exchange_token": rt,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        resp = httpx.get(platform.token_url, params=data, timeout=15)
        resp.raise_for_status()
        new_at = resp.json().get("access_token", "")
        store_token(platform.key, {"access_token": new_at})
        return new_at
    if kind in ("tiktok",):
        data = {
            "client_key": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": rt,
        }
        resp = httpx.post(platform.token_url, data=data, timeout=15)
        if resp.status_code >= 400:
            return rt
        body = resp.json().get("data", {})
        new_at = body.get("access_token", rt)
        store_token(platform.key, {"access_token": new_at, "refresh_token": body.get("refresh_token", rt)})
        return new_at
    if kind == "pinterest":
        data = {
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        resp = httpx.post(platform.token_url, data=data, timeout=15)
        if resp.status_code >= 400:
            return rt
        new_at = resp.json().get("access_token", rt)
        store_token(platform.key, {"access_token": new_at, "refresh_token": rt})
        return new_at
    return rt


def verify_platform(platform: Platform) -> Dict[str, Any]:
    """Prove the stored token actually works against the platform."""
    rec = get_token(platform.key)
    if not rec:
        return {"status": "not_connected"}

    at = refresh_access_token(platform)
    if not at:
        return {"status": "session_expired", "detail": "no usable token available"}

    if platform.verify_kind == "get_json" and platform.verify_url:
        try:
            headers = {"Authorization": f"Bearer {at}"}
            r = httpx.get(platform.verify_url, headers=headers, timeout=15)
            if r.status_code < 400:
                try:
                    j = r.json()
                    account = j.get("name") or j.get("login") or j.get("data", {}).get("id", "")
                    return {"status": "connected", "account": str(account) or "verified"}
                except Exception:
                    return {"status": "connected", "account": "verified"}
            else:
                return {"status": "failed", "detail": f"verify HTTP {r.status_code}"}
        except httpx.HTTPError as e:
            return {"status": "failed", "detail": f"verify error: {e}"}

    if platform.verify_kind == "aws_lwa":
        # LWA: if refresh token works, token is valid
        return {"status": "connected", "account": "LWA refresh token active"}

    # default: token presence only
    return {"status": "connected", "account": "token stored"}


def public_status(platform_key: str) -> Dict[str, Any]:
    """Masked status for the UI (no raw tokens)."""
    p = PLATFORMS.get(platform_key)
    if not p:
        return {"platform": platform_key, "status": "unknown"}

    rec = get_token(platform_key)
    base = {"platform": platform_key, "oauth_supported": p.supports_account_login, "manual_method": p.manual_method}
    if not p.supports_account_login:
        base["status"] = "manual"
        return base
    if not rec:
        base["status"] = "not_connected"
        return base
    # live check but cap it
    base["status"] = "verifying"
    res = verify_platform(p)
    base["status"] = res["status"]
    base["detail"] = res.get("detail", "")
    if res.get("account"):
        base["account"] = res["account"]
    if rec.get("connected_at"):
        base["connected_at"] = rec["connected_at"]
    return base


def all_platforms_status() -> List[Dict[str, Any]]:
    out = []
    for key in PLATFORMS:
        out.append(public_status(key))
    return out
