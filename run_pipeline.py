#!/usr/bin/env python3
"""Run the pipeline against a local audio sample or a URL for manual testing.

Writes repository.json and chapters_to_verify.json so verify.py can be run afterwards:

    make test-pipeline
    make run-chapter URL=https://www.archive.org/download/.../chapter.mp3
    make verify
"""
import argparse
import sys
from pathlib import Path

import static_ffmpeg

static_ffmpeg.add_paths()

import repository
from analyzer import ChapterMetadata, run_pipeline
from audio_fetcher import AudioFetcher

_DEFAULT_AUDIO_SAMPLE = Path("audio_samples/prideandprejudice_01-03_austen_1min.wav")
_DEFAULT_LISTEN_URL = (
    "https://www.archive.org/download/pride_and_prejudice_librivox/"
    "prideandprejudice_01-03_austen_64kb.mp3"
)


def _run(audio_path: str, listen_url: str) -> None:
    file_name = listen_url.rstrip("/").split("/")[-1]
    chapter_title = Path(file_name).stem

    print(f"Running pipeline on {listen_url} ...")
    meta = ChapterMetadata(
        chapter_index=1,
        chapter_title=chapter_title,
        listen_url=listen_url,
        file_name=file_name,
    )
    result = run_pipeline(audio_path, meta)

    print(f"  skip_seconds : {result.exact_audio_skip_seconds}")
    print(f"  anchor_word  : {result.detected_disclaimer_anchor_word}")
    print(f"  is_outlier   : {result.is_outlier}")

    entry = {
        "book_metadata": {
            "librivox_project_id": 0,
            "gutenberg_text_id": None,
            "title": chapter_title,
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
        [{"listen_url": meta.listen_url, "chapter_title": meta.chapter_title, "title": chapter_title}],
        Path("chapters_to_verify.json"),
    )

    print("\nWrote repository.json and chapters_to_verify.json.")
    print("Run  make verify  to open the verification UI.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pipeline on a chapter URL or local file.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url", default=None, help="Chapter audio URL to download and process")
    group.add_argument("--file", type=Path, default=None, help="Local audio file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    if args.url:
        with AudioFetcher.fetch(args.url) as tmp_path:
            _run(tmp_path, args.url)
    elif args.file:
        if not args.file.exists():
            print(f"Error: file not found at {args.file}")
            sys.exit(1)
        _run(str(args.file), str(args.file))
    else:
        # default: hardcoded sample
        if not _DEFAULT_AUDIO_SAMPLE.exists():
            print(f"Error: audio sample not found at {_DEFAULT_AUDIO_SAMPLE}")
            sys.exit(1)
        _run(str(_DEFAULT_AUDIO_SAMPLE), _DEFAULT_LISTEN_URL)


if __name__ == "__main__":
    main()
