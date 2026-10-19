"""Celery task queue for background automation jobs.

Shift-aware scheduling:
  - Work hours: 07:00-18:00, 22:00-07:00
  - Humanized delays: 5-17 min between posts
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Optional

import os
from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger("task_queue")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Celery app
app = Celery(
    "affiliate_automation",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Configuration
app.conf.update(
    result_expires=3600,  # 1 hour
    task_acks_late=True,
    task_reject_on_worker_lose=False,
    worker_concurrency=4,
    # Shift-aware schedule
    beat_schedule={
        # Morning shift start
        "scrape-at-07": {
            "task": "scrape.marketplace_products",
            "schedule": crontab(minute=0, hour=7),
        },
        # Lunch break skip
        "post-during-work-hours": {
            "task": "distribute.product_content",
            "schedule": crontab(minute=30, hour=range(9, 18)),
        },
        # Evening shift
        "post-evening": {
            "task": "distribute.product_content",
            "schedule": crontab(minute=0, hour=range(22, 24)),
            "options": {"time_limit": 300},
        },
        # Late night
        "post-late-night": {
            "task": "distribute.product_content",
            "schedule": crontab(minute=0, hour=range(0, 7)),
        },
        # Daily content refresh
        "refresh-spintax-templates": {
            "task": "refresh.spintax_templates",
            "schedule": crontab(minute=0, hour=6),
        },
    },
)


# Tasks

@app.task(name="scrape.marketplace_products", bind=True, max_retries=3)
def scrape_marketplace_products(self, marketplace: str = "tokopedia"):
    """Trigger a scrape cycle for the given marketplace."""
    from services.scrapers.scraper import ProductScraper

    logger.info("Task: scraping %s", marketplace)
    scraper = ProductScraper(marketplace)
    products = scraper.run_scrape_cycle()

    # Queue distribution tasks with humanized delays
    for i, product in enumerate(products):
        delay = random.randint(5, 17)  # 5-17 min
        schedule_distribution.delay(i, product, delay)
        logger.info(
            "Queued distribution for product #%d: %s (+%d min)",
            i, product.get("title", "unknown")[:50], delay,
        )

    return {"marketplace": marketplace, "scraped": len(products)}


@app.task(name="distribute.product_content", bind=True)
def schedule_distribution(
    self,
    index: int,
    product: Dict,
    delay_minutes: int = 0,
    platform: str = "X",
):
    """Distribute product content to target platform with delay."""
    from services.distribution.distributor import ContentDistributor
    from services.anti_banned.link_cloak import LinkCloaker

    distributor = ContentDistributor()
    cloaker = LinkCloaker(enable_cloak=True)

    # Generate content via AI
    from services.ai_engine.ai_engine import AITextEngine
    ai_engine = AITextEngine()

    hashtags = ai_engine.generate_hashtags(product)
    caption = ai_engine.generate_product_caption(product, hashtags, platform)

    # Cloak the affiliate link
    affiliate_url = product.get("url", "")
    cloaked_link = cloaker.cloak(affiliate_url)

    # Distribute
    content = {
        "caption": caption,
        "hashtags": hashtags,
        "link": cloaked_link,
        "image_url": product.get("image_url"),
        "platform": platform,
        "product": product,
    }

    result = distributor.distribute(content)
    logger.info("Distributed to %s: %s", platform, result)

    # Push to GitHub
    from services.storage.github_integrator.integrator import GitHubIntegrator
    integrator = GitHubIntegrator(
        token="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",
        author="Ayusha Shafira",
    )
    integrator.push_content(
        {**content, "thread": [content["caption"]]},
        product.get("title", "unknown"),
    )

    return {"index": index, "platform": platform, "success": True}


@app.task(name="refresh.spintax_templates", bind=True)
def refresh_spintax_templates(self):
    """Daily refresh of spintax template variations."""
    import json
    from pathlib import Path

    template_path = Path("data/spin-templates/daily.json")
    template_path.parent.mkdir(parents=True, exist_ok=True)

    base_templates = [
        "WOW {title} just got {adjective} cheaper - check it out!",
        "I found {title} at {price} and I'm not lying, it's a steal.",
        "Stop paying full price for {title} - this deal is real.",
        "If you've been looking for {title}, now's the time. {price} only!",
    ]

    from services.anti_banned.spintax import SpintaxEngine
    engine = SpintaxEngine()

    variations = []
    for template in base_templates:
        # Generate 5 variations each
        variations.extend(engine.randomize_text(template, variations=5))

    data = {
        "date": datetime.now().isoformat(),
        "count": len(variations),
        "templates": variations,
    }

    template_path.write_text(json.dumps(data, indent=2))
    logger.info("Refreshed %d spintax templates", len(variations))

    return {"count": len(variations)}
