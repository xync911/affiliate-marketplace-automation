"""Affiliate Marketplace Live Scraper.

Extracts products from Tokopedia/Shopee/Lazada using Playwright with
rotating proxies and human-like delays.
"""

import random
import time
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

try:
    from services.scrapers.proxy_utils import get_working_proxy
except ImportError:
    from proxy_utils import get_working_proxy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s - %(message)s",
)
logger = logging.getLogger("scraper")

BASE_URLS = {
    "tokopedia": "https://www.tokopedia.com",
    "shopee": "https://www.shopee.co.id",
    "lazada": "https://www.lazada.com.ph",
}


class ProductScraper:
    def __init__(self, marketplace_id="tokopedia"):
        if marketplace_id not in BASE_URLS:
            raise ValueError(f"Unknown marketplace: {marketplace_id}")
        self.marketplace_id = marketplace_id
        self.base_url = BASE_URLS[marketplace_id]
        self.product_data = []

    def _human_delay(self, min_delay=5, max_delay=17):
        delay = random.uniform(min_delay, max_delay)
        logger.debug("Sleeping %.2f seconds (humanized)", delay)
        time.sleep(delay)

    def _scrape_tokopedia(self, page):
        page.goto(f"{self.base_url}/search?q=laptop", timeout=60000)
        self._human_delay()

        products = page.query_selector_all(
            ".css-1ha0g87, .css-1k9w403, .css-1vq6z0y"
        )
        logger.info("Found %d product cards on Tokopedia", len(products))

        for product in products:
            try:
                title_el = product.query_selector(".css-1q267x9, .css-1n904kq")
                price_el = product.query_selector(".css-1v0l3j7, .css-1n904kq")
                img_el = product.query_selector(
                    ".css-1ha0g87 img, .css-87s1l0 img"
                )
                link_el = product.query_selector("a")

                if not all([title_el, price_el, img_el, link_el]):
                    continue

                self.product_data.append({
                    "title": title_el.text_content().strip(),
                    "price": price_el.text_content().strip(),
                    "image_url": img_el.get_attribute("src"),
                    "url": link_el.get_attribute("href"),
                    "marketplace": self.marketplace_id,
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            except Exception as e:
                logger.warning("Failed to parse Tokopedia product: %s", e)
                continue

    def _scrape_shopee(self, page):
        page.goto(f"{self.base_url}/search?q=laptop", timeout=60000)
        self._human_delay()

        products = page.query_selector_all(".css-1rp17rv, .css-nspwke")
        logger.info("Found %d product cards on Shopee", len(products))

        for product in products:
            try:
                title_el = product.query_selector(".css-1mf9o79, .css-1n904kq")
                price_el = product.query_selector(".css-ns362r, .css-1n904kq")
                img_el = product.query_selector("img")
                link_el = product.query_selector("a")

                if not all([title_el, price_el, img_el, link_el]):
                    continue

                self.product_data.append({
                    "title": title_el.text_content().strip(),
                    "price": price_el.text_content().strip(),
                    "image_url": img_el.get_attribute("src"),
                    "url": link_el.get_attribute("href"),
                    "marketplace": self.marketplace_id,
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            except Exception as e:
                logger.warning("Failed to parse Shopee product: %s", e)
                continue

    def _scrape_lazada(self, page):
        page.goto(f"{self.base_url}/search?q=laptop", timeout=60000)
        self._human_delay()

        products = page.query_selector_all(".css-2ce3wi, .css-1qsinh1")
        logger.info("Found %d product cards on Lazada", len(products))

        for product in products:
            try:
                title_el = product.query_selector(".css-1vq6z0y, .css-1n904kq")
                price_el = product.query_selector(".css-1qsinh1 .css-1q267x9")
                img_el = product.query_selector("img")
                link_el = product.query_selector("a")

                if not all([title_el, price_el, img_el, link_el]):
                    continue

                self.product_data.append({
                    "title": title_el.text_content().strip(),
                    "price": price_el.text_content().strip(),
                    "image_url": img_el.get_attribute("src"),
                    "url": link_el.get_attribute("href"),
                    "marketplace": self.marketplace_id,
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            except Exception as e:
                logger.warning("Failed to parse Lazada product: %s", e)
                continue

    def _scrape_products(self):
        with sync_playwright() as p:
            proxy = get_working_proxy()
            launch_opts = {"headless": True}
            if proxy:
                launch_opts["proxy"] = {"server": proxy}

            browser = p.chromium.launch(**launch_opts)
            context = browser.new_context()
            page = context.new_page()

            try:
                logger.info("Navigating to %s (proxy=%s)", self.base_url, proxy)
                scraper = getattr(self, f"_scrape_{self.marketplace_id}")
                scraper(page)
                return self.product_data
            except Exception as e:
                logger.error("Scraping failed: %s", e, exc_info=True)
                return []
            finally:
                context.close()
                browser.close()

    def run_scrape_cycle(self, min_delay=5, max_delay=17):
        """Run a full scrape cycle with human-like delays."""
        self._human_delay(min_delay, max_delay)
        logger.info("Starting scrape cycle for %s", self.marketplace_id)
        self.product_data = []
        self._scrape_products()
        logger.info("Scraping complete. Found %d products", len(self.product_data))
        return self.product_data


def main():
    scraper = ProductScraper("tokopedia")
    products = scraper.run_scrape_cycle()
    print(f"Total products scraped: {len(products)}")
    return products


if __name__ == "__main__":
    main()
