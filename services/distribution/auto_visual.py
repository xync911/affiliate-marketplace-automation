"""Auto-visual: Pillow-based image enhancement for product photos.

Adds:
  - Promo badge overlay (price, discount label)
  - Brand watermark
  - Auto-resize to platform resolution
"""

import logging
import math
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from PIL.ImageOps import exif_transpose

logger = logging.getLogger("auto_visual")

# Common platform resolutions
PLATFORM_RESOLUTIONS = {
    "X": {"width": 1200, "height": 675},   # 16:9
    "Facebook": {"width": 1200, "height": 1200},
    "TikTok": {"width": 1080, "height": 1920},  # Vertical
    "Threads": {"width": 1080, "height": 1920},  # Vertical
}

# Placeholder fonts - use system fonts in production
FONT_PATENTS = [
    "/usr/share/fonts/trioan/DejaVuSans-Bold.ttf",
]


class AutoVisualGenerator:
    def __init__(self):
        self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        try:
            for font_path in FONT_PATENTS:
                if Path(font_path).exists():
                    self.fonts["header"] = ImageFont.truetype(font_path, 40)
                    self.fonts["badge"] = ImageFont.truetype(font_path, 24)
                    self.fonts["text"] = ImageFont.truetype(font_path, 20)
        except Exception as e:
            logger.warning("Font loading failed: %s", e)

    def process_product_image(
        self,
        image_path: str,
        promo_labels: Optional[Dict[str, str]] = None,
        output_dir: str = "data/output/images",
    ) -> str:
        """Process a product image with auto-visual enhancements."""
        img = Image.open(image_path)
        img = exif_transpose(img)

        width, height = img.size
        platform = "X"

        # Resize to target resolution
        target_res = PLATFORM_RESOLUTIONS.get(platform, {})
        if target_res:
            new_w, new_h = target_res["width"], target_res["height"]
            # Preserve aspect ratio (letterbox if needed)
            scale = min(new_w / width, new_h / height)
            new_w = int(width * scale)
            new_h = int(height * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        # Add brightness/contrast enhancement
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.15)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.10)

        # Create overlay canvas for badges
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Draw bottom-right promo badge
        if promo_labels:
            x = img.width - 300
            y = img.height - 120
            self._draw_badge(draw, x, y, promo_labels)

        # Draw top-left title text
        if self.fonts.get("header"):
            bbox = draw.textbbox((0, 0), title, font=self.fonts["header"])
            tw = bbox[2] - bbox[0]
            draw.text((20, 20), title, fill=(255, 255, 255, 230), font=self.fonts["header"])

        final = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        # Save
        output_path = Path(output_dir) / f"{promo_labels or ''}_{Path(image_path).stem}.png"
        final.save(str(output_path), quality=95)
        logger.info("Processed image saved: %s", output_path)
        return str(output_path)

    def _draw_badge(self, draw, x, y, labels: Dict[str, str]):
        """Draw a promo badge on the image."""
        badge_text = labels.get("badge", "")
        promo = labels.get("promo", "")
        bg_color = (175, 55, 35, 230)  # Dark red background
        text_color = (255, 255, 255, 255)

        # Badge dimensions
        tw = max(len(badge_text) * 22 + len(promo) * 18, 300)
        th = 60

        # Draw rounded rectangle
        draw.rounded_rectangle(
            [x, y, x + tw, y + th], radius=12, fill=bg_color
        )

        # Center the text
        text_x = x + 20
        text_y = y + 10

        if badge_text:
            draw.text((text_x, text_y), badge_text, fill=text_color, font=self.fonts.get("badge"))
        if promo:
            draw.text(
                (text_x, text_y + 28), promo, fill=text_color, font=self.fonts.get("badge")
            )


def generate_thread_carousel(
    images: List[str],
    caption: str,
    out_dir: str = "data/output/images",
) -> List[str]:
    """Generate carousel images for TikTok/Threads."""
    generated = []
    for i, img_path in enumerate(images[:5]):
        visual = AutoVisualGenerator()
        label = {"price": "POT", "promo": f"Slide {i+1}"}
        out = visual.process_product_image(
            img_path,
            promo_labels=label,
            output_dir=out_dir,
        )
        generated.append(out)
    return generated
