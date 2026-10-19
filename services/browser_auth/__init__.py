"""Browser-based account login for platforms without public OAuth.

This module uses Playwright to open Chrome with a persistent user data directory.
The user logs in manually once, then the session (cookies) is saved and reused.

⚠️  Risiko: Platform bisa detect browser automation. Jika login sering gagal,
akun bisa di-suspend. Gunakan dengan bijak.

Platforms supported: X (Twitter), TikTok, Instagram, Facebook, YouTube, Pinterest
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from playwright.async_api import async_playwright

from utils.logger import logger

PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "browser_profiles"
PROFILES_DIR.mkdir(exist_ok=True)

SESSION_TIMEOUT_S = 24 * 60 * 60  # 24 hours

_pending: Dict[str, Dict] = {}


@dataclass
class PlatformAuth:
    key: str
    name: str
    login_url: str
    check_selector: str  # CSS selector that appears after successful login
    redirect_on_success: str = ""  # URL to redirect after login (optional)


PLATFORMS: Dict[str, PlatformAuth] = {
    "twitter": PlatformAuth(
        key="twitter",
        name="X (Twitter)",
        login_url="https://x.com/login",
        check_selector='[data-testid="primaryColumn"]',
    ),
    "tiktok": PlatformAuth(
        key="tiktok",
        name="TikTok",
        login_url="https://www.tiktok.com/login",
        check_selector='[data-e2e="user-info"]',
    ),
    "instagram": PlatformAuth(
        key="instagram",
        name="Instagram",
        login_url="https://www.instagram.com/accounts/login",
        check_selector='[data-visualcompletion="loading-state"]',
    ),
    "facebook": PlatformAuth(
        key="facebook",
        name="Facebook",
        login_url="https://www.facebook.com/login",
        check_selector='[data-pagelet="Feedx"]',
    ),
    "youtube": PlatformAuth(
        key="youtube",
        name="YouTube",
        login_url="https://accounts.google.com/ServiceLogin",
        check_selector='[id="account-overflow-menu"]',
    ),
    "pinterest": PlatformAuth(
        key="pinterest",
        name="Pinterest",
        login_url="https://www.pinterest.com/login",
        check_selector='[data-test-id="pin-create-button"]',
    ),
}


def _get_profile_path(platform_key: str) -> Path:
    return PROFILES_DIR / f"{platform_key}_session.json"


def _load_profile(platform_key: str) -> Optional[Dict]:
    path = _get_profile_path(platform_key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        created = data.get("created_at", "")
        if created:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - created_dt).total_seconds()
            if age > SESSION_TIMEOUT_S:
                logger.warning(f"Profile {platform_key} expired ({age:.0f}s old)")
                return None
        return data
    except Exception as e:
        logger.error(f"Error loading profile {platform_key}: {e}")
        return None


def _save_profile(platform_key: str, cookies: list) -> Dict:
    data = {
        "platform": platform_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cookies": cookies,
    }
    path = _get_profile_path(platform_key)
    path.write_text(json.dumps(data, indent=2))
    logger.info(f"Profile {platform_key} saved to {path}")
    return data


async def _login_platform(platform_key: str, redirect_url: str) -> Dict:
    """Connect to shared Chrome in the browser_login container via CDP,
    open the platform login page, user logs in manually, then save session.

    Flow:
    1. Attach to Chrome at CDP_ENDPOINT (default http://browser_login:9222)
    2. Open a new tab with platform.login_url
    3. Poll until login indicator appears OR 600s timeout
    4. Save cookies for the platform domain to config/browser_profiles/
    """
    platform = PLATFORMS.get(platform_key)
    if not platform:
        return {"error": f"Unknown platform '{platform_key}'"}

    cdp_endpoint = os.environ.get("CDP_ENDPOINT", "http://browser_login:9222")

    try:
        async with async_playwright() as p:
            # Attach to the shared browser (no persistent context here —
            # Chrome itself keeps its profile in the browser_login volume)
            browser = await p.chromium.connect_over_cdp(cdp_endpoint)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            await page.goto(platform.login_url, wait_until="domcontentloaded")
            logger.info(f"Opened {platform.login_url} in shared Chrome. User should log in at http://localhost:6080")

            # Wait for user to finish login
            try:
                await page.wait_for_selector(platform.check_selector, timeout=600000)
            except Exception:
                # Could not detect success — just save what we have
                logger.warning(f"Login selector not found for {platform_key}; saving session as-is")

            cookies = await context.cookies()
            await page.close()
            await browser.close()

            profile = _save_profile(platform_key, cookies)
            return {"status": "connected", "profile": profile}

    except Exception as e:
        logger.error(f"Browser login failed for {platform_key}: {e}")
        return {"error": f"Browser login failed: {e}"}


async def login_with_browser(platform_key: str) -> Dict:
    """Public API to start browser login flow."""
    return await _login_platform(platform_key, "")


def get_status(platform_key: str) -> Dict:
    """Check if profile exists and is valid."""
    platform = PLATFORMS.get(platform_key)
    if not platform:
        return {"platform": platform_key, "status": "unknown", "oauth_supported": False}

    profile = _load_profile(platform_key)
    if not profile:
        return {"platform": platform_key, "status": "not_connected", "oauth_supported": False}

    return {
        "platform": platform_key,
        "status": "connected",
        "oauth_supported": False,  # browser login, not OAuth
        "connected_at": profile.get("created_at", ""),
        "account": "browser_session",
    }


def all_platforms_status() -> list:
    """Get status for all platforms."""
    return [get_status(k) for k in PLATFORMS]


def clear_profile(platform_key: str) -> bool:
    """Remove stored session."""
    path = _get_profile_path(platform_key)
    if path.exists():
        path.unlink()
        return True
    return False
