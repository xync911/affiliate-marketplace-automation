"""Distributor: post content to X, Facebook, TikTok/Threads."""

import logging
import time
import random
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger("distributor")


class Platform(str, Enum):
    X = "X"
    FACEBOOK = "Facebook"
    TIKTOK = "TikTok"
    THREADS = "Threads"


class ContentDistributor:
    def __init__(
        self,
        simulate_only: bool = True,  # Set False for live posting
    ):
        self.simulate_only = simulate_only
        self.last_post_time = 0
        self.min_delay_seconds = 300  # 5 min minimum between posts
        self.max_delay_seconds = 1020  # 17 min maximum

    def distribute(self, content: Dict) -> Dict:
        """Distribute content across target platforms."""
        platform = content.get("platform", "X").upper()
        success = {}

        if platform == "X":
            success["x"] = self._post_to_x(content)
        elif platform == "Facebook":
            success["facebook"] = self._post_to_facebook(content)
        elif platform in ("TikTok", "Threads"):
            success["tiktok"] = self._post_to_tiktok(content)

        self._apply_human_delay()
        return success

    def _post_to_x(self, content: Dict) -> Dict:
        """Post thread to X (Twitter): images + thread, reply with link."""
        captions = content.get("caption", "")
        hashtags = content.get("hashtags", [])
        image_url = content.get("image_url")
        link = content.get("link", "")
        title = content.get("product", {}).get("title", "unknown")[:50]

        # Simulate or execute X posting
        if self.simulate_only:
            logger.info("[SIM] Would post to X: %s", title)
            logger.info("[SIM] Caption: %s", captions[:100])
            logger.info("[SIM] Hashtags: %s", hashtags)
            return {"status": "simulated", "platform": "X"}

        # TODO: Integrate with Twitter API v2
        # response = twikit.Tweet(
        #     text=f"{captions}\n\n{hashtags_str}",
        #     media_ids=[media_id]  # Upload image first
        # )

        return {
            "status": "error",
            "message": "X API integration not yet configured",
        }

    def _post_to_facebook(self, content: Dict) -> Dict:
        """Post to Facebook as grid with detailed review."""
        caption = content.get("caption", "")
        image_url = content.get("image_url")
        title = content.get("product", {}).get("title", "unknown")
        page_name = content.get("page_name", "@AyushaBusinessPage")

        if self.simulate_only:
            logger.info("[SIM] Would post to Facebook: %s", title)
            return {"status": "simulated", "platform": "Facebook"}

        return {"status": "error", "message": "Facebook API not yet configured"}

    def _post_to_tiktok(self, content: Dict) -> Dict:
        """Upload carousel to TikTok/Threads."""
        image_urls = [content.get("image_url")]
        caption = content.get("caption", "")

        if self.simulate_only:
            logger.info("[SIM] Would post to TikTok: %s", caption[:50])
            return {"status": "simulated", "platform": "TikTok"}

        return {"status": "error", "message": "TikTok API not yet configured"}

    def _apply_human_delay(self):
        """Apply humanized delay between posts."""
        delay = random.randint(
            self.min_delay_seconds,
            self.max_delay_seconds
        )
        logger.info("Human delay: %d seconds", delay)
        time.sleep(delay)

    def check_posting_window(self) -> bool:
        """Check if current time falls within allowed posting hours."""
        now = datetime.now()
        hour = now.hour

        # Shift 1: 07:00-18:00
        shift_1 = 7 <= hour <= 18
        # Shift 2: 22:00-07:00
        shift_2 = hour >= 22 or hour < 7

        return shift_1 or shift_2
