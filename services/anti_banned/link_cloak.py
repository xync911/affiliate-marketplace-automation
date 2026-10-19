"""Link cloaking: intercept affiliate URLs through a landing page.

Prevents shadowban on platforms that flag direct marketplace links.
"""

import logging
import uuid
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger("link_cloak")


class LinkCloaker:
    def __init__(
        self,
        landing_base: str = "https://your-landing-page.com/r/",
        enable_cloak: bool = True,
    ):
        self.landing_base = landing_base
        self.enable_cloak = enable_cloak

    def cloak(self, affiliate_url: str, ref: Optional[str] = None) -> str:
        """Return cloaked URL for the given affiliate link."""
        if not self.enable_cloak:
            return affiliate_url

        ref_id = ref or uuid.uuid4().hex[:12]
        encoded = quote(affiliate_url, safe="")
        return f"{self.landing_base}{ref_id}/{encoded}"

    def uncloak(self, cloaked_url: str) -> str:
        """Extract the original affiliate URL from a cloaked link."""
        if not self.enable_cloak:
            return cloaked_url

        path = cloaked_url.replace(self.landing_base, "").rstrip("/")
        # path = <ref_id>/<encoded_url>
        if "/" in path:
            encoded = path.split("/", 1)[1]
            from urllib.parse import unquote
            return unquote(encoded)
        return cloaked_url


def cloak_for_platform(affiliate_url: str, platform: str, cloaker: LinkCloaker) -> str:
    """Platform-specific cloaking strategy."""
    if platform == "X":
        # X thread: post image + thread, reply with cloaked link
        return cloaker.cloak(affiliate_url, ref="x-thread")
    if platform == "Facebook":
        return cloaker.cloak(affiliate_url, ref="fb-grid")
    if platform in ("TikTok", "Threads"):
        return cloaker.cloak(affiliate_url, ref="tt-carousel")
    return cloaker.cloak(affiliate_url)
