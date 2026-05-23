#!/usr/bin/env python3
"""Run the pipeline against a local audio sample for manual testing.

Writes repository.json and chapters_to_verify.json so verify.py can be run afterwards:

    make test-pipeline
    make verify
"""
import json
import sys
from pathlib import Path

import static_ffmpeg

static_ffmpeg.add_paths()

import repository
from analyzer import ChapterMetadata, run_pipeline

AUDIO_SAMPLE = Path("audio_samples/prideandprejudice_01-03_austen_1min.wav")
LISTEN_URL = (
    "https://www.archive.org/download/pride_and_prejudice_librivox/"
    "prideandprejudice_01-03_austen_64kb.mp3"
)


def main() -> None:
    if not AUDIO_SAMPLE.exists():
        print(f"Error: audio sample not found at {AUDIO_SAMPLE}")
        sys.exit(1)

    print(f"Running pipeline on {AUDIO_SAMPLE} ...")
    meta = ChapterMetadata(
        chapter_index=1,
        chapter_title="Pride and Prejudice - Chapters 1-3",
        listen_url=LISTEN_URL,
        file_name=AUDIO_SAMPLE.name,
    )
    result = run_pipeline(str(AUDIO_SAMPLE), meta)

    print(f"  skip_seconds : {result.exact_audio_skip_seconds}")
    print(f"  anchor_word  : {result.detected_disclaimer_anchor_word}")
    print(f"  is_outlier   : {result.is_outlier}")

    entry = {
        "book_metadata": {
            "librivox_project_id": 1709,
            "gutenberg_text_id": "1342",
            "title": "Pride and Prejudice",
        },
        "chapter": {
            "file_name": meta.file_name,
            "chapter_index": meta.chapter_index,
            "chapter_title": meta.chapter_title,
            "listen_url": meta.listen_url,
            "exact_audio_skip_seconds": result.exact_audio_skip_seconds,
            "detected_disclaimer_anchor_word": result.detected_disclaimer_anchor_word,
            "is_outlier": result.is_outlier,
            "verified": False,
        },
    }
    repository.upsert(entry)
    from verify.candidates import add_new_chapters
    add_new_chapters(
        [{"listen_url": meta.listen_url, "chapter_title": meta.chapter_title, "title": "Pride and Prejudice"}],
        Path("chapters_to_verify.json"),
    )

    print("\nWrote repository.json and chapters_to_verify.json.")
    print("Run  make verify  to open the verification UI.")


if __name__ == "__main__":
    main()
