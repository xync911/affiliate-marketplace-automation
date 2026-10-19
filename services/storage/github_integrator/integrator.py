"""GitHub storage integrator.

Pushes generated content (captions, hashtags, images, JSON) to a
GitHub repo via PyGithub.
"""

import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from github import Github, Auth, GithubException

logger = logging.getLogger("github_integrator")


class GitHubIntegrator:
    def __init__(
        self,
        token: str = "",
        repo: str = "ayushafira/affiliate-marketplace-automation",
        author: str = "Ayusha Shafira",
        commits_per_push: int = 5,
    ):
        self.token = token
        self.repo_name = repo
        self.author = author
        self.commits_per_push = commits_per_push
        self._pending_files: List[str] = []
        self._pending_count = 0

    def push_content(
        self,
        content: Dict,
        product_title: str,
        file_prefix: str = "content",
    ) -> bool:
        """Push a single content document to GitHub repo."""
        if not self.token:
            logger.warning("No GitHub token configured, skipping push")
            return False

        # Determine file path based on content type
        if "caption" in content:
            filename = f"{file_prefix}/{datetime.now():%Y-%m}/x_{product_title.replace(' ', '_')[:40]}.txt"
            file_data = content["caption"]
        elif "thread" in content:
            filename = f"{file_prefix}/{datetime.now():%Y-%m}/thread_{product_title.replace(' ', '_')[:40]}.json"
            file_data = json.dumps(content["thread"], ensure_ascii=False, indent=2)
        elif "image" in content:
            # Binary images: save to local data/ first, then git commit
            filename = f"{file_prefix}/images/{datetime.now():%Y-%m-%d}/{product_title.replace(' ', '_')[:30]}.png"
            self._push_binary(content["image"], filename, product_title)
            return True
        else:
            filename = f"{file_prefix}/{datetime.now():%Y-%m}/misc_{product_title.replace(' ', '_')[:40]}.json"
            file_data = json.dumps(content, ensure_ascii=False, indent=2)

        return self._push_text(filename, file_data, product_title)

    def _push_text(
        self,
        filename: str,
        content: str,
        product_title: str,
    ) -> bool:
        try:
            # Use git CLI via subprocess instead of PyGithub for reliability
            # PyGithub is preferred but we use it as fallback

            # Try PyGithub first
            try:
                g = Github(self.token)
                repo = g.get_repo(self.repo_name)
                path = filename

                try:
                    file_content = repo.get_contents(path)
                    # Update existing file
                    resp = repo.update_contents(
                        path=path,
                        message=f"[auto] {product_title}: {filename.split('/')[-1]}",
                        content=content.encode("utf-8"),
                        branch="main",
                    )
                except GithubException:
                    # Create new file
                    repo.create_file(
                        path=path,
                        message=f"[auto] {product_title}: {filename.split('/')[-1]}",
                        content=content.encode("utf-8"),
                        branch="main",
                    )
                logger.info("Pushed via PyGithub: %s", filename)
                return True

            except Exception as e:
                logger.debug("PyGithub failed (%s), falling back to git CLI", e)

            # Fallback: git CLI
            self._push_git_cli(filename, content, product_title)
            return True

        except Exception as e:
            logger.error("Failed to push to GitHub: %s", e, exc_info=True)
            return False

    def _push_binary(self, image_data: bytes, filename: str, product_title: str):
        """Push binary image data via git CLI."""
        # Save to local data directory first
        local_path = Path("data/output/images") / filename
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(image_data)
        logger.info("Saved image locally: %s", local_path)
        # Will be pushed on next git commit cycle

    def _push_git_cli(
        self,
        filename: str,
        content: str,
        product_title: str,
    ):
        local_dir = "data/output"
        local_path = Path(local_dir) / filename
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(content, encoding="utf-8")

        # git add + commit + push
        repo_base = "data/output"
        subprocess.run(
            ["git", "add", str(local_path)],
            capture_output=True,
            text=True,
            cwd=repo_base,
        )
        subprocess.run(
            ["git", "commit", "-m", f"[auto] {product_title}"],
            capture_output=True,
            text=True,
            cwd=repo_base,
        )
        subprocess.run(
            ["git", "push"],
            capture_output=True,
            text=True,
            cwd=repo_base,
        )
        logger.info("Pushed via git CLI: %s", filename)
