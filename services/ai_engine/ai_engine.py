"""AI Engine: Ollama-powered text generation for dynamic affiliate content."""

import json
import logging
import time
from typing import List, Dict, Optional

import requests

try:
    from services.anti_banned.spintax import SpintaxEngine
except ImportError:
    from services.anti_banned.spintax import SpintaxEngine

logger = logging.getLogger("ai_engine")


class OllamaEngine:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def generate_text(
        self,
        prompt: str,
        system_prompt: str = "You are an affiliate marketing copywriter.",
        json_format: bool = False,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        if json_format:
            payload["format"] = "json"

        url = f"{self.base_url}/api/generate"
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "")

    def is_available(self) -> bool:
        try:
            response = requests.get(
                f"{self.base_url}/api/tags", timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False


class AITextEngine:
    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
    ):
        self.engine = OllamaEngine(
            base_url=ollama_base_url, model=model
        )
        self.spintax = SpintaxEngine()

    def generate_product_caption(
        self,
        product: Dict,
        hashtags: List[str],
        platform: str = "X",
    ) -> str:
        prompt = self._build_caption_prompt(product, hashtags, platform)
        raw = self.engine.generate_text(
            prompt=prompt,
            system_prompt=(
                "You are an Indonesian affiliate marketing copywriter. "
                "Write concise, engaging social media captions."
            ),
        )
        return self.spintax.process(raw)

    def generate_thread(
        self,
        product: Dict,
        hashtags: List[str],
        thread_length: int = 3,
    ) -> List[str]:
        prompt = self._build_thread_prompt(product, hashtags, thread_length)
        raw = self.engine.generate_text(
            prompt=prompt,
            json_format=True,
            system_prompt=(
                "Generate a social media thread as JSON: "
                '{"posts": ["post1", "post2", ...]}'
            ),
        )
        try:
            data = json.loads(raw)
            posts = data.get("posts", [raw])
        except json.JSONDecodeError:
            logger.warning("Failed to parse thread JSON, using raw: %s", raw)
            posts = [raw]

        return [self.spintax.process(post) for post in posts]

    def generate_hashtags(
        self,
        product: Dict,
        count: int = 5,
    ) -> List[str]:
        prompt = (
            f"Generate {count} relevant Indonesian hashtags for: "
            f"{product.get('title', '')}\n"
            f"Price: {product.get('price', 'N/A')}\n"
            f"Output as JSON array."
        )
        raw = self.engine.generate_text(
            prompt=prompt, json_format=True
        )
        try:
            tags = json.loads(raw)
            if isinstance(tags, list):
                return [t.strip() for t in tags[:count]]
        except json.JSONDecodeError:
            pass
        return ["#promo", "#diskon", "#jokerpromo", "#affiliate", "#murah"]

    def generate_visual_labels(
        self,
        product: Dict,
        promo_text: Optional[str] = None,
    ) -> Dict[str, str]:
        """Return label configs for Pillow auto-visual generation."""
        prompt = (
            f"Generate promotional label text for product: "
            f"{product.get('title', '')}\n"
            f"Price: {product.get('price', 'N/A')}\n"
            f"Output JSON: {{'badge': 'short text', 'promo': 'promo phrase'}}"
        )
        raw = self.engine.generate_text(
            prompt=prompt, json_format=True
        )
        try:
            labels = json.loads(raw)
            if "badge" not in labels:
                labels["badge"] = product.get("price", "PROMO")
            if "promo" not in labels:
                labels["promo"] = promo_text or "DISKON BESAR!"
            return labels
        except json.JSONDecodeError:
            return {
                "badge": product.get("price", "PROMO"),
                "promo": promo_text or "DISKON BESAR!",
            }

    # --- Private helpers ---

    def _build_caption_prompt(
        self, product: Dict, hashtags: List[str], platform: str
    ) -> str:
        style_hints = {
            "X": "punchy, short, uses line breaks, ends with question",
            "Facebook": "detailed, informative, friendly tone, 3-5 paragraphs",
            "TikTok": "casual, trendy, uses slang, under 150 words",
        }
        style = style_hints.get(platform, "engaging")
        return (
            f"Write a {platform} caption for:\n"
            f"Product: {product.get('title', '')}\n"
            f"Price: {product.get('price', 'N/A')}\n"
            f"Marketplace: {product.get('marketplace', 'N/A')}\n"
            f"Hashtags to include: {', '.join(hashtags)}\n"
            f"Style: {style}\n"
            "Do not include the affiliate link in the caption."
        )

    def _build_thread_prompt(
        self, product: Dict, hashtags: List[str], thread_length: int
    ) -> str:
        return (
            f"Create a {thread_length}-post thread for:\n"
            f"Product: {product.get('title', '')}\n"
            f"Price: {product.get('price', 'N/A')}\n"
            f"Hashtags: {', '.join(hashtags)}\n"
            "Post 1: hook + image placeholder\n"
            "Post 2: features + benefits\n"
            "Post 3: call-to-action + link placeholder\n"
            "Output strict JSON."
        )
