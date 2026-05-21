"""Repository module — owns all reads and writes to repository.json."""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, model_validator

REPOSITORY_PATH = Path("repository.json")


class BookMetadata(BaseModel):
    librivox_project_id: int
    gutenberg_text_id: Optional[str]
    title: str


class ChapterEntry(BaseModel):
    file_name: str
    chapter_index: int
    chapter_title: str
    listen_url: str
    exact_audio_skip_seconds: float
    detected_disclaimer_anchor_word: Optional[str]
    is_outlier: bool
    verified: bool


class UpsertPayload(BaseModel):
    book_metadata: BookMetadata
    chapter: ChapterEntry


def load(path: Path = REPOSITORY_PATH) -> dict:
    """Return the full repository dict. Returns empty dict if file doesn't exist."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def upsert(entry: dict, path: Path = REPOSITORY_PATH) -> None:
    """Add or update a chapter entry matched by listen_url. Atomic write."""
    payload = UpsertPayload(**entry)
    project_id = str(payload.book_metadata.librivox_project_id)

    repo = load(path)

    if project_id not in repo:
        repo[project_id] = {
            "book_metadata": payload.book_metadata.model_dump(),
            "chapters": [],
        }

    chapters = repo[project_id]["chapters"]
    listen_url = payload.chapter.listen_url
    chapter_dict = payload.chapter.model_dump()

    for i, ch in enumerate(chapters):
        if ch["listen_url"] == listen_url:
            chapters[i] = chapter_dict
            break
    else:
        chapters.append(chapter_dict)

    _atomic_write(repo, path)


def mark_verified(listen_url: str, path: Path = REPOSITORY_PATH) -> None:
    """Set verified=True on the chapter matching listen_url. Atomic write."""
    repo = load(path)

    for book in repo.values():
        for chapter in book["chapters"]:
            if chapter["listen_url"] == listen_url:
                chapter["verified"] = True
                _atomic_write(repo, path)
                return

    raise KeyError(f"listen_url not found: {listen_url}")


def contains(listen_url: str, path: Path = REPOSITORY_PATH) -> bool:
    """Return True if a chapter with the given listen_url exists."""
    repo = load(path)
    for book in repo.values():
        for chapter in book["chapters"]:
            if chapter["listen_url"] == listen_url:
                return True
    return False


def _atomic_write(data: dict, path: Path) -> None:
    """Write data to path atomically via a temp file + rename."""
    dir_ = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
