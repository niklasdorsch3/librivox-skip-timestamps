"""Tests for validate_contribution.py — all boundary cases per acceptance criteria."""

import json
import pytest
from pipeline.validate_contribution import (
    build_comment,
    count_verified,
    find_new_chapters,
    load_json,
)


def make_chapter(url: str, verified: bool = False) -> dict:
    return {
        "file_name": "ch01.mp3",
        "chapter_index": 1,
        "chapter_title": "Chapter 1",
        "listen_url": url,
        "exact_audio_skip_seconds": 5.1,
        "detected_disclaimer_anchor_word": "domain",
        "is_outlier": False,
        "verified": verified,
    }


def make_repo(chapters: list) -> dict:
    return {
        "1": {
            "book_metadata": {
                "librivox_project_id": 1,
                "title": "Test Book",
                "gutenberg_text_id": None,
            },
            "chapters": chapters,
        }
    }


# --- find_new_chapters ---


class TestFindNewChapters:
    def test_all_new_when_base_empty(self):
        pr_repo = make_repo([make_chapter("http://a.mp3"), make_chapter("http://b.mp3")])
        new = find_new_chapters(pr_repo, {})
        assert len(new) == 2

    def test_no_new_when_identical(self):
        repo = make_repo([make_chapter("http://a.mp3")])
        assert find_new_chapters(repo, repo) == []

    def test_only_added_chapters_returned(self):
        base = make_repo([make_chapter("http://a.mp3")])
        pr = make_repo([make_chapter("http://a.mp3"), make_chapter("http://b.mp3")])
        new = find_new_chapters(pr, base)
        assert len(new) == 1
        assert new[0]["listen_url"] == "http://b.mp3"

    def test_exactly_100_new(self):
        chapters = [make_chapter(f"http://ch{i}.mp3") for i in range(100)]
        new = find_new_chapters(make_repo(chapters), {})
        assert len(new) == 100

    def test_exactly_101_new(self):
        chapters = [make_chapter(f"http://ch{i}.mp3") for i in range(101)]
        new = find_new_chapters(make_repo(chapters), {})
        assert len(new) == 101

    def test_no_changes(self):
        assert find_new_chapters({}, {}) == []


# --- count_verified ---


class TestCountVerified:
    def test_all_verified(self):
        chapters = [make_chapter(f"http://ch{i}.mp3", verified=True) for i in range(5)]
        assert count_verified(chapters) == 5

    def test_none_verified(self):
        chapters = [make_chapter(f"http://ch{i}.mp3", verified=False) for i in range(5)]
        assert count_verified(chapters) == 0

    def test_mixed(self):
        chapters = [make_chapter(f"http://ch{i}.mp3", verified=(i < 3)) for i in range(5)]
        assert count_verified(chapters) == 3

    def test_exactly_9_verified(self):
        chapters = [make_chapter(f"http://ch{i}.mp3", verified=True) for i in range(9)]
        assert count_verified(chapters) == 9

    def test_exactly_10_verified(self):
        chapters = [make_chapter(f"http://ch{i}.mp3", verified=True) for i in range(10)]
        assert count_verified(chapters) == 10


# --- build_comment ---


class TestBuildComment:
    def test_no_warnings_when_within_limits(self):
        comment = build_comment(total_new=50, verified=15)
        assert "✓" in comment
        assert "⚠️" not in comment

    def test_warning_over_100_entries(self):
        comment = build_comment(total_new=101, verified=15)
        assert "⚠️" in comment
        assert "101" in comment
        assert "100 entries" in comment

    def test_exactly_100_no_warning(self):
        comment = build_comment(total_new=100, verified=15)
        assert "More than 100" not in comment

    def test_warning_under_10_verified(self):
        comment = build_comment(total_new=50, verified=9)
        assert "⚠️" in comment
        assert "9" in comment
        assert "10 verified" in comment

    def test_exactly_10_verified_no_warning(self):
        comment = build_comment(total_new=50, verified=10)
        assert "Fewer than 10" not in comment

    def test_both_warnings(self):
        comment = build_comment(total_new=101, verified=9)
        assert comment.count("⚠️") == 2

    def test_no_changes_no_warnings(self):
        comment = build_comment(total_new=0, verified=0)
        assert "⚠️" not in comment

    def test_comment_always_shows_counts(self):
        comment = build_comment(total_new=5, verified=3)
        assert "5" in comment
        assert "3" in comment


# --- load_json ---


class TestLoadJson:
    def test_loads_existing_file(self, tmp_path):
        f = tmp_path / "repo.json"
        f.write_text('{"key": "value"}')
        assert load_json(str(f)) == {"key": "value"}

    def test_returns_empty_dict_for_missing_file(self, tmp_path):
        assert load_json(str(tmp_path / "missing.json")) == {}

    def test_returns_empty_dict_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("")
        assert load_json(str(f)) == {}
