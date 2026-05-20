"""Tests for the Repository module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import repository


BOOK_META = {
    "librivox_project_id": 119,
    "gutenberg_text_id": None,
    "title": "The Art of War",
}

CHAPTER_1 = {
    "file_name": "art_of_war_01_sun_tzu.mp3",
    "chapter_index": 1,
    "chapter_title": "Chapter 1: The Laying of Plans",
    "listen_url": "https://librivox.org/chapter/1",
    "approximate_text_end": 14.21,
    "exact_audio_skip_seconds": 15.15,
    "detected_disclaimer_anchor_word": "domain",
    "is_outlier": False,
    "verified": False,
}

CHAPTER_2 = {
    "file_name": "art_of_war_02_sun_tzu.mp3",
    "chapter_index": 2,
    "chapter_title": "Chapter 2: Waging War",
    "listen_url": "https://librivox.org/chapter/2",
    "approximate_text_end": 12.50,
    "exact_audio_skip_seconds": 13.00,
    "detected_disclaimer_anchor_word": None,
    "is_outlier": False,
    "verified": False,
}


def _entry(chapter: dict, meta: dict = BOOK_META) -> dict:
    return {"book_metadata": meta, "chapter": chapter}


@pytest.fixture
def repo_path(tmp_path) -> Path:
    return tmp_path / "repository.json"


class TestLoad:
    def test_returns_empty_dict_when_file_missing(self, repo_path):
        assert repository.load(repo_path) == {}

    def test_returns_existing_data(self, repo_path):
        data = {"119": {"book_metadata": BOOK_META, "chapters": []}}
        repo_path.write_text(json.dumps(data))
        assert repository.load(repo_path) == data


class TestContains:
    def test_returns_false_for_missing_url(self, repo_path):
        assert repository.contains("https://librivox.org/chapter/1", repo_path) is False

    def test_returns_true_after_upsert(self, repo_path):
        repository.upsert(_entry(CHAPTER_1), repo_path)
        assert repository.contains(CHAPTER_1["listen_url"], repo_path) is True

    def test_returns_false_for_different_url(self, repo_path):
        repository.upsert(_entry(CHAPTER_1), repo_path)
        assert repository.contains(CHAPTER_2["listen_url"], repo_path) is False


class TestUpsert:
    def test_adds_new_chapter(self, repo_path):
        repository.upsert(_entry(CHAPTER_1), repo_path)
        repo = repository.load(repo_path)
        assert len(repo["119"]["chapters"]) == 1
        assert repo["119"]["chapters"][0]["listen_url"] == CHAPTER_1["listen_url"]

    def test_adds_second_chapter_same_book(self, repo_path):
        repository.upsert(_entry(CHAPTER_1), repo_path)
        repository.upsert(_entry(CHAPTER_2), repo_path)
        repo = repository.load(repo_path)
        assert len(repo["119"]["chapters"]) == 2

    def test_updates_existing_chapter_by_listen_url(self, repo_path):
        repository.upsert(_entry(CHAPTER_1), repo_path)
        updated = {**CHAPTER_1, "exact_audio_skip_seconds": 99.9}
        repository.upsert(_entry(updated), repo_path)
        repo = repository.load(repo_path)
        assert len(repo["119"]["chapters"]) == 1
        assert repo["119"]["chapters"][0]["exact_audio_skip_seconds"] == 99.9

    def test_accepts_null_gutenberg_text_id(self, repo_path):
        repository.upsert(_entry(CHAPTER_1), repo_path)
        repo = repository.load(repo_path)
        assert repo["119"]["book_metadata"]["gutenberg_text_id"] is None

    def test_accepts_null_detected_disclaimer_anchor_word(self, repo_path):
        repository.upsert(_entry(CHAPTER_2), repo_path)
        repo = repository.load(repo_path)
        assert repo["119"]["chapters"][0]["detected_disclaimer_anchor_word"] is None

    def test_rejects_missing_required_chapter_field(self, repo_path):
        bad_chapter = {k: v for k, v in CHAPTER_1.items() if k != "listen_url"}
        with pytest.raises(Exception):
            repository.upsert(_entry(bad_chapter), repo_path)

    def test_rejects_missing_required_metadata_field(self, repo_path):
        bad_meta = {k: v for k, v in BOOK_META.items() if k != "title"}
        with pytest.raises(Exception):
            repository.upsert(_entry(CHAPTER_1, bad_meta), repo_path)


class TestMarkVerified:
    def test_sets_verified_true(self, repo_path):
        repository.upsert(_entry(CHAPTER_1), repo_path)
        repository.mark_verified(CHAPTER_1["listen_url"], repo_path)
        repo = repository.load(repo_path)
        assert repo["119"]["chapters"][0]["verified"] is True

    def test_raises_for_unknown_listen_url(self, repo_path):
        with pytest.raises(KeyError):
            repository.mark_verified("https://librivox.org/nonexistent", repo_path)


class TestAtomicWrite:
    def test_file_written_and_readable(self, repo_path):
        repository.upsert(_entry(CHAPTER_1), repo_path)
        assert repo_path.exists()
        repo = repository.load(repo_path)
        assert "119" in repo

    def test_original_file_intact_on_mid_write_crash(self, repo_path):
        """A failed rename must not corrupt the existing file."""
        repository.upsert(_entry(CHAPTER_1), repo_path)
        original_content = repo_path.read_text()

        with patch("os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                repository.upsert(_entry(CHAPTER_2), repo_path)

        assert repo_path.read_text() == original_content

    def test_no_temp_file_left_after_crash(self, repo_path):
        """Temp file must be cleaned up after a failed rename."""
        repository.upsert(_entry(CHAPTER_1), repo_path)

        with patch("os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                repository.upsert(_entry(CHAPTER_2), repo_path)

        tmp_files = list(repo_path.parent.glob("*.tmp"))
        assert tmp_files == []
