"""Batch Runner — processes LibriVox books from data/books.txt."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests
import static_ffmpeg

static_ffmpeg.add_paths()

import pipeline.repository as repository
from pipeline.analyzer import AnchorWordNotFoundError, ChapterMetadata, run_pipeline
from pipeline.audio_fetcher import AudioFetcher

LIBRIVOX_API_BASE = "https://librivox.org/api/feed/audiobooks"
BOOKS_FILE = Path("data/books.txt")
REPOSITORY_FILE = Path("data/repository.json")
CHAPTERS_TO_VERIFY_FILE = Path("data/chapters_to_verify.json")


def fetch_book_info(book_id: int, session: requests.Session) -> dict:
    """Fetch book metadata from the LibriVox API."""
    url = f"{LIBRIVOX_API_BASE}/?id={book_id}&format=json"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    books = resp.json().get("books", [])
    if not books:
        raise ValueError(f"Book {book_id} not found in LibriVox API")
    return books[0]


def fetch_chapters(rss_url: str, session: requests.Session) -> list[dict]:
    """Parse the LibriVox RSS feed and return a list of chapter dicts."""
    resp = session.get(rss_url, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    channel = root.find("channel")
    chapters = []
    index = 1
    for item in channel.findall("item"):
        title = item.findtext("title", "")
        enclosure = item.find("enclosure")
        if enclosure is None:
            continue
        listen_url = enclosure.get("url", "")
        if not listen_url:
            continue
        file_name = listen_url.rstrip("/").split("/")[-1]
        chapters.append(
            {
                "chapter_index": index,
                "chapter_title": title,
                "listen_url": listen_url,
                "file_name": file_name,
            }
        )
        index += 1
    return chapters


def main(
    books_file: Path = BOOKS_FILE,
    repo_path: Path = REPOSITORY_FILE,
    verify_file: Path = CHAPTERS_TO_VERIFY_FILE,
    session: Optional[requests.Session] = None,
    limit: Optional[int] = None,
) -> None:
    """Read data/books.txt, process each chapter, write results to data/repository.json."""
    if session is None:
        session = requests.Session()

    book_ids = [
        int(line.strip())
        for line in books_file.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    total = 0
    succeeded = 0
    no_disclaimer = 0
    failed = 0
    failed_chapters: list[tuple[str, str, str]] = []
    new_chapters_to_verify: list[dict] = []

    for book_id in book_ids:
        try:
            book_info = fetch_book_info(book_id, session)
        except Exception as exc:
            print(f"✗ Book {book_id} — failed to fetch metadata: {exc}")
            continue

        title = book_info.get("title", f"Book {book_id}")
        rss_url = book_info.get("url_rss", "")
        gutenberg_text_id: Optional[str] = book_info.get("url_project") or None

        try:
            chapters = fetch_chapters(rss_url, session)
        except Exception as exc:
            print(f"✗ {title} — failed to fetch chapters: {exc}")
            continue

        for chapter in chapters:
            if limit is not None and total >= limit:
                break


            listen_url = chapter["listen_url"]
            chapter_title = chapter["chapter_title"]

            if repository.contains(listen_url, repo_path):
                continue

            total += 1

            try:
                chapter_meta = ChapterMetadata(
                    chapter_index=chapter["chapter_index"],
                    chapter_title=chapter_title,
                    listen_url=listen_url,
                    file_name=chapter["file_name"],
                )

                with AudioFetcher.fetch(listen_url, session) as audio_path:
                    result = run_pipeline(audio_path, chapter_meta)

                entry = {
                    "book_metadata": {
                        "librivox_project_id": book_id,
                        "gutenberg_text_id": gutenberg_text_id,
                        "title": title,
                    },
                    "chapter": {
                        "file_name": chapter["file_name"],
                        "chapter_index": chapter["chapter_index"],
                        "chapter_title": chapter_title,
                        "listen_url": listen_url,
                        "exact_audio_skip_seconds": result.exact_audio_skip_seconds,
                        "detected_disclaimer_anchor_word": result.detected_disclaimer_anchor_word,
                        "is_outlier": result.is_outlier,
                        "verified": result.verified,
                    },
                }
                repository.upsert(entry, repo_path)
                new_chapters_to_verify.append({
                        "listen_url": listen_url,
                        "chapter_title": chapter_title,
                        "title": title,
                    })

                if result.exact_audio_skip_seconds == 0.0:
                    print(f"~ {title} — {chapter_title} (no disclaimer)")
                    no_disclaimer += 1
                else:
                    print(f"✓ {title} — {chapter_title}")
                    succeeded += 1

            except Exception as exc:
                reason = str(exc) or type(exc).__name__
                print(f"✗ {title} — {chapter_title} — {reason}")
                failed += 1
                failed_chapters.append((title, chapter_title, reason))

        if limit is not None and total >= limit:
            break

    from verify.candidates import add_new_chapters
    add_new_chapters(new_chapters_to_verify, verify_file)

    print(
        f"\nSummary: {total} processed, {succeeded} succeeded, "
        f"{no_disclaimer} no-disclaimer, {failed} failed"
    )
    if failed_chapters:
        print("Failed chapters:")
        for fail_title, fail_chapter, reason in failed_chapters:
            print(f"  ✗ {fail_title} — {fail_chapter}: {reason}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process LibriVox books from data/books.txt.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Stop after processing N chapters (default: no limit).",
    )
    args = parser.parse_args()
    main(limit=args.limit)
