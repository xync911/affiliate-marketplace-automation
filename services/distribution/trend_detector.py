"""Trend detection: trigger content immediately when trending topics appear.

Uses simulated X/Twitter trending topics API and paces content generation.
"""

import json
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("trend_detector")


class TrendTrigger:
    def __init__(self, trend_file: str = "data/trending.json"):
        self.trends_file = Path(trend_file)
        self.active_trends: Dict[str, str] = {}
        self.last_trigger_time: Optional[datetime] = None
        self.min_cooldown_seconds = 300  # 5 min between triggers

    def check_and_trigger(self, products: List[Dict]) -> List[Dict]:
        """Check if any trending topic matches our products."""
        triggered = []

        # In production: fetch real trends from X API
        trends = self._fetch_current_trends()

        matching = [p for p in products if self._match_products_to_trends(p, trends)]

        if matching and products:
            logger.info(
                "Trend match! %d of %d products match trending topics",
                len(matching), len(products),
            )
            # Immediately queue distribution for matched products
            from services.task_queue.worker import schedule_distribution
            for product in matching:
                schedule_distribution.delay(
                    index=-1, product=product, delay_minutes=random.randint(5, 10)
                )
                triggered.append({"product": product["title"], "reason": "trend_match"})

        return triggered

    def _fetch_current_trends(self) -> Dict[str, str]:
        """Fetch current trending topics.

        In production: X API v2 GET /trending_trends?ids=[...]
        Simulated version reads from local file.
        """
        if self.trends_file.exists():
            try:
                data = json.loads(self.trends_file.read_text())
                return data.get("trends", [])
            except Exception:
                pass

        # Simulated trending keywords
        simulated = [
            {"keyword": "#laptopdiskon", "count": 150000},
            {"keyword": "#bajaukota", "count": 89000},
            {"keyword": "#promoakbatas", "count": 56000},
            {"keyword": "#summerdeals", "count": 120000},
            {"keyword": "#birthdaygifts", "count": 78000},
        ]
        return {t["keyword"]: t["count"] for t in simulated}

    def _match_products_to_trends(self, product: Dict, trends: Dict) -> bool:
        """Check if product title matches a trending keyword."""
        title = product.get("title", "").lower()
        keywords = list(trends.keys())
        return any(kw in title for kw in keywords)

    def update_trends(self, new_trends: Dict[str, str]):
        """Save updated trends to file."""
        data = {"date": datetime.now().isoformat(), "trends": list(new_trends.items())}
        self.trends_file.parent.mkdir(parents=True, exist_ok=True)
        self.trends_file.write_text(json.dumps(data, indent=2))
        logger.info("Updated trending file with %d trends", len(new_trends))
