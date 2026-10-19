"""Spintax engine for anti-duplicate content generation."""

import random
import re
import logging
from typing import List

logger = logging.getLogger("spintax")

# Spintax syntax: {option1|option2|option3}
# Nested: {option1|{option2a|option2b}|option3}

class SpintaxEngine:
    def __init__(self):
        # Cache of pre-processed spintax templates
        self._cache = {}

    def process(self, text: str) -> str:
        """Process spintax syntax: replace {opt1|opt2|opt3} with random choice."""
        if not text:
            return text

        result = text
        max_iterations = 10
        iteration = 0

        while "{" in result and "}" in result and iteration < max_iterations:
            # Find innermost spintax block (no nested braces inside)
            pattern = r"\{([^{}]*)\}"
            match = re.search(pattern, result)

            if not match:
                break

            inner = match.group(1)
            options = self._split_options(inner)

            if len(options) > 1:
                choice = random.choice(options)
                result = result.replace(match.group(0), choice, 1)
            else:
                result = result.replace(match.group(0), inner, 1)

            iteration += 1

        return result

    def _split_options(self, text: str) -> List[str]:
        """Split spintax options, handling nested braces."""
        options = []
        current = []
        depth = 0

        for char in text:
            if char == "{" and depth == 0:
                depth = 1
                current.append(char)
            elif char == "}" and depth > 0:
                depth -= 1
                current.append(char)
                if depth == 0:
                    options.append("".join(current))
                    current = []
            elif char == "|" and depth == 0:
                options.append("".join(current))
                current = []
            else:
                current.append(char)

        if current:
            options.append("".join(current))

        return options

    def randomize_text(
        self,
        template: str,
        variations: int = 5,
    ) -> List[str]:
        """Generate multiple variations of a spintext template."""
        return [self.process(template) for _ in range(variations)]

    def is_duplicate(self, text: str, existing: List[str]) -> bool:
        """Check if text is a duplicate of existing content."""
        normalized = text.lower().strip()
        for existing_text in existing:
            if existing_text.lower().strip() == normalized:
                return True
        return False

    def deduplicate_hashtags(
        self,
        hashtags: List[str],
        used: List[str],
        keep_count: int = 3,
    ) -> List[str]:
        """Filter out already-used hashtags, keep requested count."""
        fresh = [h for h in hashtags if h.lower() not in {u.lower() for u in used}]
        if len(fresh) < keep_count:
            fresh.extend(hashtags[:keep_count - len(fresh)])
        return fresh[:keep_count]
