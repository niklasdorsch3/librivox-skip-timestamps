"""Verification session — tracks state across browser approve/deny actions."""

from typing import Callable, Optional

from .candidates import REQUIRED_VERIFICATIONS


class VerificationSession:
    """State for a single verification run."""

    def __init__(
        self,
        chapters: list[dict],
        on_approve: Callable[[str], None],
        on_deny: Callable[[str], None],
        all_entries: list[dict] | None = None,
        override: bool = False,
    ) -> None:
        self.chapters = chapters
        self._on_approve = on_approve
        self._on_deny = on_deny
        self.override = override
        self.current_index = 0
        self.approved = 0
        self.status = "active"
        self.message = ""
        self._all_entries: list[dict] = [dict(e) for e in (all_entries or [])]

    def current_chapter(self) -> Optional[dict]:
        if self.current_index < len(self.chapters):
            return self.chapters[self.current_index]
        return None

    def approve(self) -> None:
        if self.status != "active":
            return
        chapter = self.chapters[self.current_index]
        url = chapter["listen_url"]
        self._on_approve(url)
        self._update_entry_status(url, "approved")
        self.approved += 1
        self.current_index += 1
        if self.current_index >= len(self.chapters):
            self._check_completion()

    def deny(self) -> None:
        chapter = self.chapters[self.current_index]
        url = chapter["listen_url"]
        self._on_deny(url)
        self._update_entry_status(url, "denied")
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
        counts: dict[str, int] = {"approved": 0, "denied": 0, "pending": 0}
        denied_chapters = []
        for e in self._all_entries:
            s = e.get("verification_status", "pending")
            counts[s] = counts.get(s, 0) + 1
            if s == "denied":
                denied_chapters.append({
                    "listen_url": e.get("listen_url", ""),
                    "chapter_title": e.get("chapter_title", ""),
                    "title": e.get("title", ""),
                })
        return {"counts": counts, "denied_chapters": denied_chapters}

    def _update_entry_status(self, url: str, status: str) -> None:
        for entry in self._all_entries:
            if entry["listen_url"] == url:
                entry["verification_status"] = status
                return

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
                f"Only {total_approved} {chapter_word} approved, {total_denied} denied. "
                f"A high denial rate mean the pipeline is producing inaccurate results — "
                f"cannot submit."
            )
