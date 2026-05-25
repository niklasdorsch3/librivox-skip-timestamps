"""Candidate loading, selection, and status tracking for verification."""

import json
import random
import sys
from pathlib import Path
from typing import Literal

import pipeline.repository as repository

CHAPTERS_TO_VERIFY_FILE = Path("data/chapters_to_verify.json")
REPOSITORY_FILE = Path("data/repository.json")
REQUIRED_VERIFICATIONS = 10

VerificationStatus = Literal["pending", "approved", "denied"]

LEVER_MAP: dict[str, str] = {
    "wrong_anchor_word":   "OLLAMA_MODEL / OPENAI_MODEL",
    "false_positive":      "CONFIDENCE_THRESHOLD",
    "false_negative":      "CONFIDENCE_THRESHOLD",
    "silence_detection":   "SILENCE_THRESHOLD_DBFS",
    "transcription_error": "WHISPER_MODEL",
}


def load_verify_file(verify_file_path: Path) -> list[dict]:
    """Load chapters_to_verify.json, supporting both old (list of URLs) and new (list of objects) formats."""
    if not verify_file_path.exists():
        return []
    raw = json.loads(verify_file_path.read_text())
    if raw and isinstance(raw[0], str):
        # Migrate old format: bare URL strings → objects
        return [
            {"listen_url": url, "chapter_title": "", "title": "", "verification_status": "pending"}
            for url in raw
        ]
    return raw


def save_verify_file(entries: list[dict], verify_file_path: Path) -> None:
    verify_file_path.write_text(json.dumps(entries, indent=2) + "\n")


def update_verification_status(
    listen_url: str,
    status: VerificationStatus,
    verify_file_path: Path,
    feedback: dict | None = None,
) -> None:
    """Update the verification_status of a single entry in-place.

    When feedback is provided (non-empty dict), denial fields are written alongside the status.
    """
    entries = load_verify_file(verify_file_path)
    for entry in entries:
        if entry["listen_url"] == listen_url:
            entry["verification_status"] = status
            if feedback:
                entry["denial_reason"] = feedback.get("denial_reason")
                entry["denial_lever"] = LEVER_MAP.get(feedback.get("denial_reason", ""), "unknown")
                entry["human_timestamp"] = feedback.get("human_timestamp")
                entry["notes"] = feedback.get("notes", "")
            break
    save_verify_file(entries, verify_file_path)


def add_new_chapters(
    new_chapters: list[dict], verify_file_path: Path
) -> None:
    """Merge new chapters into the verify file, preserving existing statuses.

    Each item in new_chapters must have: listen_url, chapter_title, title.
    Existing entries are never overwritten — only new URLs are appended.
    """
    existing = load_verify_file(verify_file_path)
    existing_urls = {e["listen_url"] for e in existing}
    for ch in new_chapters:
        if ch["listen_url"] not in existing_urls:
            existing.append({
                "listen_url": ch["listen_url"],
                "chapter_title": ch.get("chapter_title", ""),
                "title": ch.get("title", ""),
                "verification_status": "pending",
            })
    save_verify_file(existing, verify_file_path)


def load_verification_candidates(
    repo_path: Path, verify_file_path: Path
) -> list[dict]:
    """Return pending chapters with full metadata merged from repository."""
    if not verify_file_path.exists():
        print(f"Error: {verify_file_path} not found. Run main.py first.")
        sys.exit(1)

    entries = load_verify_file(verify_file_path)
    active_entries = {
        e["listen_url"]: e
        for e in entries
        if e.get("verification_status") == "pending"
    }

    if not active_entries:
        print("No chapters to verify.")
        sys.exit(0)

    repo = repository.load(repo_path)
    candidates = []

    for book_data in repo.values():
        book_meta = book_data.get("book_metadata", {})
        for chapter in book_data.get("chapters", []):
            entry = active_entries.get(chapter["listen_url"])
            if entry:
                candidates.append({
                    **chapter,
                    "title": book_meta.get("title", ""),
                    "verification_status": entry.get("verification_status", "pending"),
                })

    return candidates


def select_chapters(
    candidates: list[dict], max_count: int = REQUIRED_VERIFICATIONS
) -> list[dict]:
    """Select up to max_count chapters: all outliers first, then random non-outliers."""
    outliers = [c for c in candidates if c.get("is_outlier")]
    non_outliers = [c for c in candidates if not c.get("is_outlier")]

    random.shuffle(outliers)
    random.shuffle(non_outliers)

    selected = outliers[:max_count]
    remaining = max_count - len(selected)
    if remaining > 0:
        selected.extend(non_outliers[:remaining])

    return selected
