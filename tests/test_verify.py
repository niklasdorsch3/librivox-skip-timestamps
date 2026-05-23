"""Tests for the verify/ package — candidates, session, and server."""

import json
import threading
import urllib.request
from pathlib import Path

import pytest

import repository
from verify.candidates import (
    add_new_chapters,
    load_verification_candidates,
    load_verify_file,
    save_verify_file,
    select_chapters,
    update_verification_status,
)
from verify.session import VerificationSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chapter(i, is_outlier=False, title="A Book"):
    return {
        "file_name": f"ch{i}.mp3",
        "chapter_index": i,
        "chapter_title": f"Chapter {i}",
        "listen_url": f"http://example.com/{i}.mp3",
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


def _write_verify_file(tmp_path, entries):
    """Write a chapters_to_verify.json with the given entry list."""
    path = tmp_path / "chapters_to_verify.json"
    path.write_text(json.dumps(entries, indent=2) + "\n")
    return path


def _pending_entry(url, chapter_title="", title=""):
    return {
        "listen_url": url,
        "chapter_title": chapter_title,
        "title": title,
        "verification_status": "pending",
    }


def _make_session(tmp_path, chapters, override=False):
    repo_path = _write_repo(tmp_path, chapters)
    entries = [_pending_entry(ch["listen_url"]) for ch in chapters]
    verify_file = _write_verify_file(tmp_path, entries)
    return VerificationSession(chapters, repo_path, verify_file, override=override)


# ===========================================================================
# verify.candidates — load_verify_file
# ===========================================================================

def test_load_verify_file_returns_empty_list_when_missing(tmp_path):
    result = load_verify_file(tmp_path / "missing.json")
    assert result == []


def test_load_verify_file_new_format(tmp_path):
    entries = [_pending_entry("http://example.com/1.mp3", "Ch 1", "Book")]
    path = _write_verify_file(tmp_path, entries)
    result = load_verify_file(path)
    assert result == entries


def test_load_verify_file_migrates_old_url_list_format(tmp_path):
    """Old format is a bare list of URL strings — should be migrated to object list."""
    old_format = ["http://example.com/1.mp3", "http://example.com/2.mp3"]
    path = tmp_path / "verify.json"
    path.write_text(json.dumps(old_format))

    result = load_verify_file(path)

    assert len(result) == 2
    assert result[0]["listen_url"] == "http://example.com/1.mp3"
    assert result[0]["verification_status"] == "pending"
    assert result[1]["listen_url"] == "http://example.com/2.mp3"


# ===========================================================================
# verify.candidates — save_verify_file
# ===========================================================================

def test_save_verify_file_round_trips(tmp_path):
    entries = [_pending_entry("http://example.com/1.mp3")]
    path = tmp_path / "verify.json"
    save_verify_file(entries, path)
    assert json.loads(path.read_text()) == entries


# ===========================================================================
# verify.candidates — update_verification_status
# ===========================================================================

def test_update_verification_status_changes_matching_entry(tmp_path):
    url = "http://example.com/1.mp3"
    entries = [_pending_entry(url)]
    path = _write_verify_file(tmp_path, entries)

    update_verification_status(url, "approved", path)

    result = load_verify_file(path)
    assert result[0]["verification_status"] == "approved"


def test_update_verification_status_ignores_other_entries(tmp_path):
    url1 = "http://example.com/1.mp3"
    url2 = "http://example.com/2.mp3"
    entries = [_pending_entry(url1), _pending_entry(url2)]
    path = _write_verify_file(tmp_path, entries)

    update_verification_status(url1, "denied", path)

    result = load_verify_file(path)
    assert result[1]["verification_status"] == "pending"


# ===========================================================================
# verify.candidates — add_new_chapters
# ===========================================================================

def test_add_new_chapters_appends_new_entries(tmp_path):
    path = _write_verify_file(tmp_path, [])
    new_chapters = [{"listen_url": "http://example.com/1.mp3", "chapter_title": "Ch 1", "title": "Book"}]

    add_new_chapters(new_chapters, path)

    result = load_verify_file(path)
    assert len(result) == 1
    assert result[0]["listen_url"] == "http://example.com/1.mp3"
    assert result[0]["verification_status"] == "pending"


def test_add_new_chapters_does_not_duplicate_existing_url(tmp_path):
    url = "http://example.com/1.mp3"
    existing = [{"listen_url": url, "chapter_title": "Ch 1", "title": "Book", "verification_status": "approved"}]
    path = _write_verify_file(tmp_path, existing)

    add_new_chapters([{"listen_url": url, "chapter_title": "Ch 1", "title": "Book"}], path)

    result = load_verify_file(path)
    assert len(result) == 1
    assert result[0]["verification_status"] == "approved"  # status preserved


def test_add_new_chapters_preserves_existing_statuses(tmp_path):
    url1 = "http://example.com/1.mp3"
    url2 = "http://example.com/2.mp3"
    existing = [{"listen_url": url1, "chapter_title": "Ch 1", "title": "Book", "verification_status": "denied"}]
    path = _write_verify_file(tmp_path, existing)

    add_new_chapters([{"listen_url": url2, "chapter_title": "Ch 2", "title": "Book"}], path)

    result = load_verify_file(path)
    assert len(result) == 2
    assert result[0]["verification_status"] == "denied"
    assert result[1]["verification_status"] == "pending"


# ===========================================================================
# verify.candidates — select_chapters
# ===========================================================================

def test_select_chapters_empty():
    assert select_chapters([]) == []


def test_select_chapters_limits_to_ten():
    candidates = [_make_chapter(i) for i in range(20)]
    selected = select_chapters(candidates)
    assert len(selected) == 10


def test_select_chapters_fewer_than_max():
    candidates = [_make_chapter(i) for i in range(5)]
    selected = select_chapters(candidates)
    assert len(selected) == 5


def test_select_chapters_prioritizes_all_outliers():
    outliers = [_make_chapter(i, is_outlier=True) for i in range(3)]
    normals = [_make_chapter(i + 100) for i in range(10)]
    selected = select_chapters(outliers + normals, max_count=5)
    selected_urls = {c["listen_url"] for c in selected}
    for o in outliers:
        assert o["listen_url"] in selected_urls, "Every outlier must appear in selection"


def test_select_chapters_outliers_fill_then_normal():
    outliers = [_make_chapter(i, is_outlier=True) for i in range(8)]
    normals = [_make_chapter(i + 100) for i in range(5)]
    selected = select_chapters(outliers + normals, max_count=10)
    assert len(selected) == 10
    assert sum(1 for c in selected if c["is_outlier"]) == 8
    assert sum(1 for c in selected if not c["is_outlier"]) == 2


def test_select_chapters_all_outliers_exceed_max():
    outliers = [_make_chapter(i, is_outlier=True) for i in range(15)]
    selected = select_chapters(outliers, max_count=10)
    assert len(selected) == 10
    assert all(c["is_outlier"] for c in selected)


# ===========================================================================
# verify.candidates — load_verification_candidates
# ===========================================================================

def test_load_verification_candidates_filters_to_pending_entries(tmp_path):
    chapters = [_make_chapter(1), _make_chapter(2), _make_chapter(3)]
    repo_path = _write_repo(tmp_path, chapters)
    verify_file = _write_verify_file(tmp_path, [
        _pending_entry(chapters[0]["listen_url"]),
        _pending_entry(chapters[2]["listen_url"]),
    ])

    candidates = load_verification_candidates(repo_path, verify_file)
    urls = {c["listen_url"] for c in candidates}
    assert urls == {chapters[0]["listen_url"], chapters[2]["listen_url"]}


def test_load_verification_candidates_excludes_denied_entries(tmp_path):
    """Previously denied chapters should not re-appear — they show in the status panel instead."""
    chapters = [_make_chapter(1)]
    repo_path = _write_repo(tmp_path, chapters)
    verify_file = _write_verify_file(tmp_path, [
        {"listen_url": chapters[0]["listen_url"], "chapter_title": "", "title": "", "verification_status": "denied"},
    ])

    with pytest.raises(SystemExit) as exc_info:
        load_verification_candidates(repo_path, verify_file)
    assert exc_info.value.code == 0


def test_load_verification_candidates_excludes_approved_entries(tmp_path):
    """Approved entries have no active work — function exits cleanly (0) when none remain."""
    chapters = [_make_chapter(1)]
    repo_path = _write_repo(tmp_path, chapters)
    verify_file = _write_verify_file(tmp_path, [
        {"listen_url": chapters[0]["listen_url"], "chapter_title": "", "title": "", "verification_status": "approved"},
    ])

    with pytest.raises(SystemExit) as exc_info:
        load_verification_candidates(repo_path, verify_file)
    assert exc_info.value.code == 0


def test_load_verification_candidates_includes_book_title(tmp_path):
    chapters = [_make_chapter(1, title="Great War")]
    repo_path = _write_repo(tmp_path, chapters, title="Great War")
    verify_file = _write_verify_file(tmp_path, [_pending_entry(chapters[0]["listen_url"])])

    candidates = load_verification_candidates(repo_path, verify_file)
    assert candidates[0]["title"] == "Great War"


def test_load_verification_candidates_empty_verify_file(tmp_path):
    """Empty verify file means no work — function exits cleanly (0)."""
    chapters = [_make_chapter(1)]
    repo_path = _write_repo(tmp_path, chapters)
    verify_file = _write_verify_file(tmp_path, [])

    with pytest.raises(SystemExit) as exc_info:
        load_verification_candidates(repo_path, verify_file)
    assert exc_info.value.code == 0


def test_load_verification_candidates_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit):
        load_verification_candidates(
            tmp_path / "repository.json",
            tmp_path / "missing.json",
        )


# ===========================================================================
# verify.session — VerificationSession
# ===========================================================================

def test_session_current_chapter_none_when_empty(tmp_path):
    session = _make_session(tmp_path, [])
    assert session.current_chapter() is None


def test_session_deny_marks_chapter_and_continues(tmp_path):
    """Denying the only chapter exhausts the list and triggers completion check."""
    chapters = [_make_chapter(1)]
    session = _make_session(tmp_path, chapters)
    session.deny()
    # no approved chapters → not_enough
    assert session.status == "not_enough"
    assert session.current_index == 1


def test_session_deny_updates_verify_file(tmp_path):
    chapters = [_make_chapter(1)]
    repo_path = _write_repo(tmp_path, chapters)
    entries = [_pending_entry(chapters[0]["listen_url"])]
    verify_file = _write_verify_file(tmp_path, entries)
    session = VerificationSession(chapters, repo_path, verify_file)

    session.deny()

    result = load_verify_file(verify_file)
    assert result[0]["verification_status"] == "denied"


def test_session_approve_advances_to_next_chapter(tmp_path):
    chapters = [_make_chapter(1), _make_chapter(2)]
    session = _make_session(tmp_path, chapters)

    assert session.current_chapter()["listen_url"] == chapters[0]["listen_url"]
    session.approve()
    assert session.current_chapter()["listen_url"] == chapters[1]["listen_url"]


def test_session_approve_marks_chapter_verified_in_repo(tmp_path):
    chapters = [_make_chapter(1)]
    repo_path = _write_repo(tmp_path, chapters)
    entries = [_pending_entry(chapters[0]["listen_url"])]
    verify_file = _write_verify_file(tmp_path, entries)
    session = VerificationSession(chapters, repo_path, verify_file)

    session.approve()

    repo = repository.load(repo_path)
    assert repo["1"]["chapters"][0]["verified"] is True


def test_session_approve_updates_verify_file_status(tmp_path):
    chapters = [_make_chapter(1)]
    repo_path = _write_repo(tmp_path, chapters)
    entries = [_pending_entry(chapters[0]["listen_url"])]
    verify_file = _write_verify_file(tmp_path, entries)
    session = VerificationSession(chapters, repo_path, verify_file)

    session.approve()

    result = load_verify_file(verify_file)
    assert result[0]["verification_status"] == "approved"


def test_session_complete_after_ten_approvals(tmp_path):
    chapters = [_make_chapter(i) for i in range(10)]
    session = _make_session(tmp_path, chapters)

    for _ in range(10):
        session.approve()

    assert session.status == "complete"
    assert session.approved == 10
    assert "Ready to submit" in session.message


def test_session_not_enough_when_fewer_than_ten_no_override(tmp_path):
    chapters = [_make_chapter(i) for i in range(5)]
    session = _make_session(tmp_path, chapters, override=False)

    for _ in range(5):
        session.approve()

    assert session.status == "not_enough"
    assert "Only 5 chapters verified" in session.message
    assert "--override" in session.message


def test_session_override_completes_with_fewer_than_ten(tmp_path):
    chapters = [_make_chapter(i) for i in range(3)]
    session = _make_session(tmp_path, chapters, override=True)

    for _ in range(3):
        session.approve()

    assert session.status == "complete"
    assert session.approved == 3


def test_session_deny_then_approve_works(tmp_path):
    """deny() just skips; the next chapter can still be approved."""
    chapters = [_make_chapter(1), _make_chapter(2)]
    session = _make_session(tmp_path, chapters)

    session.deny()
    assert session.status == "active"
    session.approve()
    assert session.approved == 1


def test_session_deny_after_some_approvals(tmp_path):
    chapters = [_make_chapter(i) for i in range(5)]
    session = _make_session(tmp_path, chapters)

    session.approve()
    session.approve()
    session.deny()

    assert session.status == "active"
    assert session.approved == 2
    assert session.current_index == 3


# ===========================================================================
# verify.server — HTTP endpoints
# ===========================================================================

def _start_test_server(session):
    """Start the verification server on a random free port; return (server, url)."""
    from verify.server import _Handler, _ReuseAddrServer  # type: ignore[attr-defined]
    from verify.server import _Handler

    class _ReuseAddrServer:
        pass

    from http.server import HTTPServer

    server = HTTPServer(("localhost", 0), _Handler)
    server.session = session  # type: ignore[attr-defined]
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://localhost:{port}"


@pytest.fixture()
def server_session(tmp_path):
    """A running verification server with two chapters; yields (server, base_url, session)."""
    from http.server import HTTPServer
    from verify.server import _Handler

    chapters = [_make_chapter(1), _make_chapter(2)]
    repo_path = _write_repo(tmp_path, chapters)
    entries = [_pending_entry(ch["listen_url"]) for ch in chapters]
    verify_file = _write_verify_file(tmp_path, entries)
    session = VerificationSession(chapters, repo_path, verify_file)

    server = HTTPServer(("localhost", 0), _Handler)
    server.session = session  # type: ignore[attr-defined]
    server.allow_reuse_address = True
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, f"http://localhost:{port}", session
    server.shutdown()


def _get_json(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def _post(url):
    req = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def _post_json(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def test_server_get_session_returns_initial_state(server_session):
    _, base_url, session = server_session
    data = _get_json(f"{base_url}/api/session")

    assert data["status"] == "active"
    assert data["current_index"] == 0
    assert data["total"] == 2
    assert data["approved"] == 0
    assert data["chapter"]["listen_url"] == "http://example.com/1.mp3"


def test_server_get_root_returns_html(server_session):
    _, base_url, _ = server_session
    with urllib.request.urlopen(base_url) as r:
        assert r.status == 200
        assert b"text/html" in r.headers["Content-Type"].encode()


def test_server_post_approve_advances_session(server_session):
    _, base_url, session = server_session
    data = _post(f"{base_url}/api/approve")

    assert data["approved"] == 1
    assert data["current_index"] == 1
    assert session.approved == 1


def test_server_post_deny_advances_to_next(server_session):
    _, base_url, session = server_session
    data = _post(f"{base_url}/api/deny")

    assert data["status"] == "active"
    assert data["current_index"] == 1
    assert session.current_index == 1


def test_server_get_status_returns_counts(server_session):
    _, base_url, _ = server_session
    data = _get_json(f"{base_url}/api/status")

    assert "counts" in data
    assert "denied_chapters" in data
    counts = data["counts"]
    assert counts["pending"] == 2
    assert counts["approved"] == 0
    assert counts["denied"] == 0


def test_server_get_status_reflects_deny(server_session):
    _, base_url, _ = server_session
    _post(f"{base_url}/api/deny")
    data = _get_json(f"{base_url}/api/status")

    assert data["counts"]["denied"] == 1
    assert len(data["denied_chapters"]) == 1
    assert data["denied_chapters"][0]["listen_url"] == "http://example.com/1.mp3"


def test_server_unknown_route_returns_404(server_session):
    _, base_url, _ = server_session
    req = urllib.request.Request(f"{base_url}/api/nonexistent")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 404


# ===========================================================================
# verify.candidates — feedback in update_verification_status
# ===========================================================================

def test_update_verification_status_with_feedback_writes_denial_fields(tmp_path):
    url = "http://example.com/1.mp3"
    path = _write_verify_file(tmp_path, [_pending_entry(url)])
    feedback = {"denial_reason": "silence_detection", "human_timestamp": 20.5, "notes": "threshold too tight"}

    update_verification_status(url, "denied", path, feedback=feedback)

    entry = load_verify_file(path)[0]
    assert entry["verification_status"] == "denied"
    assert entry["denial_reason"] == "silence_detection"
    assert entry["denial_lever"] == "SILENCE_THRESHOLD_DBFS"
    assert entry["human_timestamp"] == 20.5
    assert entry["notes"] == "threshold too tight"


def test_update_verification_status_approve_has_no_feedback_fields(tmp_path):
    url = "http://example.com/1.mp3"
    path = _write_verify_file(tmp_path, [_pending_entry(url)])

    update_verification_status(url, "approved", path)

    entry = load_verify_file(path)[0]
    assert "denial_reason" not in entry
    assert "denial_lever" not in entry


def test_update_verification_status_empty_feedback_has_no_denial_fields(tmp_path):
    url = "http://example.com/1.mp3"
    path = _write_verify_file(tmp_path, [_pending_entry(url)])

    update_verification_status(url, "denied", path, feedback={})

    entry = load_verify_file(path)[0]
    assert "denial_reason" not in entry
    assert "denial_lever" not in entry


def test_lever_mapping_all_reasons():
    from verify.candidates import LEVER_MAP
    expected = {
        "wrong_anchor_word":   "OLLAMA_MODEL / OPENAI_MODEL",
        "false_positive":      "CONFIDENCE_THRESHOLD",
        "false_negative":      "CONFIDENCE_THRESHOLD",
        "silence_detection":   "SILENCE_THRESHOLD_DBFS",
        "transcription_error": "WHISPER_MODEL",
    }
    for reason, lever in expected.items():
        assert LEVER_MAP[reason] == lever


# ===========================================================================
# verify.session — deny with feedback
# ===========================================================================

def test_session_deny_with_feedback_writes_feedback(tmp_path):
    chapters = [_make_chapter(1)]
    repo_path = _write_repo(tmp_path, chapters)
    verify_file = _write_verify_file(tmp_path, [_pending_entry(chapters[0]["listen_url"])])
    session = VerificationSession(chapters, repo_path, verify_file)
    feedback = {"denial_reason": "wrong_anchor_word", "human_timestamp": 15.0, "notes": ""}

    session.deny(feedback)

    entry = load_verify_file(verify_file)[0]
    assert entry["denial_reason"] == "wrong_anchor_word"
    assert entry["denial_lever"] == "OLLAMA_MODEL / OPENAI_MODEL"
    assert entry["human_timestamp"] == 15.0


def test_session_deny_without_feedback_advances_cleanly(tmp_path):
    chapters = [_make_chapter(1), _make_chapter(2)]
    session = _make_session(tmp_path, chapters)

    session.deny({})

    assert session.current_index == 1
    assert session.status == "active"


# ===========================================================================
# verify.server — deny parses JSON body
# ===========================================================================

def test_server_deny_with_json_body_writes_feedback(server_session):
    _, base_url, session = server_session
    feedback = {"denial_reason": "silence_detection", "human_timestamp": 12.5, "notes": "test note"}

    _post_json(f"{base_url}/api/deny", feedback)

    entry = next(e for e in load_verify_file(session._verify_file) if e["verification_status"] == "denied")
    assert entry["denial_reason"] == "silence_detection"
    assert entry["denial_lever"] == "SILENCE_THRESHOLD_DBFS"
    assert entry["human_timestamp"] == 12.5
