"""Verification session — tracks state across browser approve/deny actions."""

from pathlib import Path
from typing import Optional

import repository

from .candidates import REQUIRED_VERIFICATIONS, update_verification_status


class VerificationSession:
    """State for a single verification run."""

    def __init__(
        self,
        chapters: list[dict],
        repo_path: Path,
        verify_file_path: Path,
        override: bool = False,
    ) -> None:
        self.chapters = chapters
        self.repo_path = repo_path
        self.verify_file_path = verify_file_path
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
        repository.mark_verified(chapter["listen_url"], self.repo_path)
        update_verification_status(chapter["listen_url"], "approved", self.verify_file_path)
        self.approved += 1
        self.current_index += 1
        if self.current_index >= len(self.chapters):
            self._check_completion()

    def deny(self) -> None:
        chapter = self.chapters[self.current_index]
        update_verification_status(chapter["listen_url"], "denied", self.verify_file_path)
        self.current_index += 1
        if self.current_index >= len(self.chapters):
            self._check_completion()

    def _check_completion(self) -> None:
        if self.approved >= REQUIRED_VERIFICATIONS or (
            self.override and self.approved >= 1
        ):
            self.status = "complete"
            self.message = (
                f"Verified {self.approved} chapters from "
                f"{len(self.chapters)} total new entries. Ready to submit."
            )
        else:
            self.status = "not_enough"
            self.message = (
                f"Only {self.approved} chapters verified (need 10 minimum). "
                f"Run `python verify --override` to create a PR anyway. "
                f"10 verified entries ensures quality — proceeding with fewer is not recommended."
            )
