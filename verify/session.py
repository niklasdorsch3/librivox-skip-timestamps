"""Verification session — tracks state across browser approve/deny actions."""

from pathlib import Path
from typing import Optional

import pipeline.repository as repository

from .candidates import REQUIRED_VERIFICATIONS, load_verify_file, update_verification_status


class VerificationSession:
    """State for a single verification run."""

    def __init__(
        self,
        chapters: list[dict],
        repo_path: Path,
        verify_file: Path,
        override: bool = False,
    ) -> None:
        self.chapters = chapters
        self._repo_path = repo_path
        self._verify_file = verify_file
        self.override = override
        self.current_index = 0
        self.approved = 0
        self.status = "active"
        self.message = ""

    def current_chapter(self) -> Optional[dict]:
        if self.current_index < len(self.chapters):
            return self.chapters[self.current_index]
        return None

    def approve(self) -> None:
        if self.status != "active":
            return
        chapter = self.chapters[self.current_index]
        url = chapter["listen_url"]
        repository.mark_verified(url, self._repo_path)
        update_verification_status(url, "approved", self._verify_file)
        self.approved += 1
        self.current_index += 1
        if self.current_index >= len(self.chapters):
            self._check_completion()

    def deny(self, feedback: dict | None = None) -> None:
        chapter = self.chapters[self.current_index]
        url = chapter["listen_url"]
        update_verification_status(url, "denied", self._verify_file, feedback=feedback)
        self.current_index += 1
        if self.current_index >= len(self.chapters):
            self._check_completion()

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "current_index": self.current_index,
            "total": len(self.chapters),
            "approved": self.approved,
            "chapter": self.current_chapter(),
            "message": self.message,
        }

    def status_data(self) -> dict:
        all_entries = load_verify_file(self._verify_file)
        counts: dict[str, int] = {"approved": 0, "denied": 0, "pending": 0}
        denied_chapters = []
        for e in all_entries:
            s = e.get("verification_status", "pending")
            counts[s] = counts.get(s, 0) + 1
            if s == "denied":
                denied_chapters.append({
                    "listen_url": e.get("listen_url", ""),
                    "chapter_title": e.get("chapter_title", ""),
                    "title": e.get("title", ""),
                })
        return {"counts": counts, "denied_chapters": denied_chapters}

    def _check_completion(self) -> None:
        counts = self.status_data()["counts"]
        total_approved = counts.get("approved", 0)
        total_denied = counts.get("denied", 0)
        if total_approved >= REQUIRED_VERIFICATIONS or (
            self.override and total_approved >= 1
        ):
            self.status = "complete"
            chapter_word = "chapter" if total_approved == 1 else "chapters"
            self.message = f"Verified {total_approved} {chapter_word}. Ready to submit."
        else:
            self.status = "not_enough"
            chapter_word = "chapter" if total_approved == 1 else "chapters"
            self.message = (
                f"Only {total_approved} {chapter_word} verified, {total_denied} denied. "
                f"Run with --override to submit anyway."
            )
