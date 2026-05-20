"""Tests for verify.py — Verification Script."""

import json
from pathlib import Path

import pytest

import verify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chapter(i, is_outlier=False, title="A Book"):
    return {
        "file_name": f"ch{i}.mp3",
        "chapter_index": i,
        "chapter_title": f"Chapter {i}",
        "listen_url": f"http://example.com/{i}.mp3",
        "approximate_text_end": 5.0,
        "exact_audio_skip_seconds": 11.0 if is_outlier else 5.0,
        "detected_disclaimer_anchor_word": "domain",
        "is_outlier": is_outlier,
        "verified": False,
        "title": title,
    }


def _write_repo(tmp_path, chapters, book_id=1, title="A Book"):
    """Write a valid repository.json with the given chapters."""
    repo_path = tmp_path / "repository.json"
    chapter_dicts = [
        {k: v for k, v in ch.items() if k != "title"}
        for ch in chapters
    ]
    repo_data = {
        str(book_id): {
            "book_metadata": {
                "librivox_project_id": book_id,
                "gutenberg_text_id": None,
                "title": title,
            },
            "chapters": chapter_dicts,
        }
    }
    repo_path.write_text(json.dumps(repo_data))
    return repo_path


# ---------------------------------------------------------------------------
# select_chapters
# ---------------------------------------------------------------------------

def test_select_chapters_empty():
    assert verify.select_chapters([]) == []


def test_select_chapters_limits_to_ten():
    candidates = [_make_chapter(i) for i in range(20)]
    selected = verify.select_chapters(candidates)
    assert len(selected) == 10


def test_select_chapters_fewer_than_max():
    candidates = [_make_chapter(i) for i in range(5)]
    selected = verify.select_chapters(candidates)
    assert len(selected) == 5


def test_select_chapters_prioritizes_all_outliers():
    outliers = [_make_chapter(i, is_outlier=True) for i in range(3)]
    normals = [_make_chapter(i + 100) for i in range(10)]
    selected = verify.select_chapters(outliers + normals, max_count=5)
    selected_urls = {c["listen_url"] for c in selected}
    for o in outliers:
        assert o["listen_url"] in selected_urls, "Every outlier must appear in selection"


def test_select_chapters_outliers_fill_then_normal():
    outliers = [_make_chapter(i, is_outlier=True) for i in range(8)]
    normals = [_make_chapter(i + 100) for i in range(5)]
    selected = verify.select_chapters(outliers + normals, max_count=10)
    assert len(selected) == 10
    assert sum(1 for c in selected if c["is_outlier"]) == 8
    assert sum(1 for c in selected if not c["is_outlier"]) == 2


def test_select_chapters_all_outliers_exceed_max():
    outliers = [_make_chapter(i, is_outlier=True) for i in range(15)]
    selected = verify.select_chapters(outliers, max_count=10)
    assert len(selected) == 10
    assert all(c["is_outlier"] for c in selected)


# ---------------------------------------------------------------------------
# load_verification_candidates
# ---------------------------------------------------------------------------

def test_load_verification_candidates_filters_to_verify_list(tmp_path):
    chapters = [_make_chapter(1), _make_chapter(2), _make_chapter(3)]
    repo_path = _write_repo(tmp_path, chapters)

    verify_file = tmp_path / "chapters_to_verify.json"
    verify_file.write_text(json.dumps([chapters[0]["listen_url"], chapters[2]["listen_url"]]))

    candidates = verify.load_verification_candidates(repo_path, verify_file)
    urls = {c["listen_url"] for c in candidates}
    assert urls == {chapters[0]["listen_url"], chapters[2]["listen_url"]}


def test_load_verification_candidates_includes_book_title(tmp_path):
    chapters = [_make_chapter(1, title="Great War")]
    repo_path = _write_repo(tmp_path, chapters, title="Great War")

    verify_file = tmp_path / "chapters_to_verify.json"
    verify_file.write_text(json.dumps([chapters[0]["listen_url"]]))

    candidates = verify.load_verification_candidates(repo_path, verify_file)
    assert candidates[0]["title"] == "Great War"


def test_load_verification_candidates_empty_verify_list(tmp_path):
    chapters = [_make_chapter(1)]
    repo_path = _write_repo(tmp_path, chapters)

    verify_file = tmp_path / "chapters_to_verify.json"
    verify_file.write_text("[]")

    candidates = verify.load_verification_candidates(repo_path, verify_file)
    assert candidates == []


def test_load_verification_candidates_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit):
        verify.load_verification_candidates(
            tmp_path / "repository.json",
            tmp_path / "missing.json",
        )


# ---------------------------------------------------------------------------
# _VerificationSession
# ---------------------------------------------------------------------------

def test_session_deny_sets_status():
    session = verify._VerificationSession([], Path("dummy.json"))
    session.deny()
    assert session.status == "denied"
    assert "Verification failed" in session.message


def test_session_current_chapter_none_when_empty():
    session = verify._VerificationSession([], Path("dummy.json"))
    assert session.current_chapter() is None


def test_session_current_chapter_advances_on_approve(tmp_path):
    chapters = [_make_chapter(1), _make_chapter(2)]
    repo_path = _write_repo(tmp_path, chapters)

    session = verify._VerificationSession(chapters, repo_path)
    assert session.current_chapter()["listen_url"] == chapters[0]["listen_url"]

    session.approve()
    assert session.current_chapter()["listen_url"] == chapters[1]["listen_url"]


def test_session_approve_marks_chapter_verified_in_repo(tmp_path):
    chapters = [_make_chapter(1)]
    repo_path = _write_repo(tmp_path, chapters)

    session = verify._VerificationSession(chapters, repo_path)
    session.approve()

    repo = json.loads(repo_path.read_text())
    assert repo["1"]["chapters"][0]["verified"] is True


def test_session_complete_after_ten_approvals(tmp_path):
    chapters = [_make_chapter(i) for i in range(10)]
    repo_path = _write_repo(tmp_path, chapters)

    session = verify._VerificationSession(chapters, repo_path)
    for _ in range(10):
        session.approve()

    assert session.status == "complete"
    assert session.approved == 10
    assert "Ready to submit" in session.message


def test_session_not_enough_when_fewer_than_ten_no_override(tmp_path):
    chapters = [_make_chapter(i) for i in range(5)]
    repo_path = _write_repo(tmp_path, chapters)

    session = verify._VerificationSession(chapters, repo_path, override=False)
    for _ in range(5):
        session.approve()

    assert session.status == "not_enough"
    assert "Only 5 chapters verified" in session.message
    assert "--override" in session.message


def test_session_override_completes_with_fewer_than_ten(tmp_path):
    chapters = [_make_chapter(i) for i in range(3)]
    repo_path = _write_repo(tmp_path, chapters)

    session = verify._VerificationSession(chapters, repo_path, override=True)
    for _ in range(3):
        session.approve()

    assert session.status == "complete"
    assert session.approved == 3


def test_session_deny_after_some_approvals(tmp_path):
    chapters = [_make_chapter(i) for i in range(5)]
    repo_path = _write_repo(tmp_path, chapters)

    session = verify._VerificationSession(chapters, repo_path)
    session.approve()
    session.approve()
    session.deny()

    assert session.status == "denied"
