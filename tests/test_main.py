"""Tests for main.py — Batch Runner (IS-05)."""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from analyzer import AnchorWordNotFoundError, PipelineResult
from audio_fetcher import AudioFetchError
from boundary_detector import BoundaryDetectionError
import main as m


# --- Fixtures ---

FAKE_OK = PipelineResult(
    exact_audio_skip_seconds=14.5,
    detected_disclaimer_anchor_word="domain",
    is_outlier=False,
)
FAKE_NO_DISC = PipelineResult(
    exact_audio_skip_seconds=0.0,
    detected_disclaimer_anchor_word=None,
    is_outlier=False,
)

BOOK_INFO = {"id": "101", "title": "Test Book", "url_rss": "http://rss/101"}


def make_rss(*chapters):
    items = "".join(
        f"<item><title>{ch['title']}</title>"
        f"<enclosure url=\"{ch['url']}\" length=\"100000\" type=\"audio/mpeg\"/>"
        f"</item>"
        for ch in chapters
    )
    return (
        '<?xml version="1.0"?><rss version="2.0">'
        f"<channel>{items}</channel></rss>"
    )


@contextmanager
def fake_fetch(url, session=None):
    yield "/tmp/fake.mp3"


def setup_files(tmp_path, book_ids):
    books_file = tmp_path / "books.txt"
    books_file.write_text("\n".join(str(b) for b in book_ids) + "\n")
    return books_file, tmp_path / "repository.json", tmp_path / "verify.json"


# --- fetch_book_info ---

class TestFetchBookInfo:
    def test_calls_correct_url(self):
        session = MagicMock()
        session.get.return_value.json.return_value = {
            "books": [{"id": "42", "title": "T", "url_rss": "http://r"}]
        }
        m.fetch_book_info(42, session)
        url = session.get.call_args[0][0]
        assert "42" in url
        assert "format=json" in url

    def test_returns_first_book(self):
        session = MagicMock()
        session.get.return_value.json.return_value = {
            "books": [{"id": "1", "title": "First"}, {"id": "2", "title": "Second"}]
        }
        assert m.fetch_book_info(1, session)["title"] == "First"

    def test_raises_if_no_books(self):
        session = MagicMock()
        session.get.return_value.json.return_value = {"books": []}
        with pytest.raises(ValueError, match="not found"):
            m.fetch_book_info(999, session)


# --- fetch_chapters ---

class TestFetchChapters:
    def test_parses_chapters(self):
        session = MagicMock()
        session.get.return_value.text = make_rss(
            {"title": "Chapter 1", "url": "https://ia.org/ch1.mp3"},
            {"title": "Chapter 2", "url": "https://ia.org/ch2.mp3"},
        )
        chapters = m.fetch_chapters("http://rss", session)
        assert len(chapters) == 2
        assert chapters[0]["chapter_title"] == "Chapter 1"
        assert chapters[0]["listen_url"] == "https://ia.org/ch1.mp3"
        assert chapters[0]["file_name"] == "ch1.mp3"
        assert chapters[0]["chapter_index"] == 1
        assert chapters[1]["chapter_index"] == 2

    def test_skips_item_without_enclosure(self):
        rss = (
            '<?xml version="1.0"?><rss version="2.0"><channel>'
            "<item><title>No audio</title></item>"
            "<item><title>With audio</title>"
            '<enclosure url="https://ia.org/x.mp3" length="1" type="audio/mpeg"/>'
            "</item></channel></rss>"
        )
        session = MagicMock()
        session.get.return_value.text = rss
        chapters = m.fetch_chapters("http://rss", session)
        assert len(chapters) == 1
        assert chapters[0]["chapter_title"] == "With audio"

    def test_skips_item_with_empty_url(self):
        rss = (
            '<?xml version="1.0"?><rss version="2.0"><channel>'
            "<item><title>Empty URL</title>"
            '<enclosure url="" length="1" type="audio/mpeg"/>'
            "</item></channel></rss>"
        )
        session = MagicMock()
        session.get.return_value.text = rss
        chapters = m.fetch_chapters("http://rss", session)
        assert len(chapters) == 0


# --- main() ---

CH1 = {"chapter_index": 1, "chapter_title": "Ch 1",
        "listen_url": "http://a.org/ch1.mp3", "file_name": "ch1.mp3"}
CH2 = {"chapter_index": 2, "chapter_title": "Ch 2",
        "listen_url": "http://a.org/ch2.mp3", "file_name": "ch2.mp3"}
CH3 = {"chapter_index": 3, "chapter_title": "Ch 3",
        "listen_url": "http://a.org/ch3.mp3", "file_name": "ch3.mp3"}


class TestMain:
    def test_reads_all_book_ids(self, tmp_path):
        books_file, repo, verify = setup_files(tmp_path, [101, 202])
        with patch.object(m, "fetch_book_info") as mock_book, \
             patch.object(m, "fetch_chapters", return_value=[]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert"), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            mock_book.return_value = BOOK_INFO
            m.main(books_file, repo, verify)
        assert mock_book.call_count == 2
        assert mock_book.call_args_list[0][0][0] == 101
        assert mock_book.call_args_list[1][0][0] == 202

    def test_skips_already_processed_chapter(self, tmp_path):
        books_file, repo, verify = setup_files(tmp_path, [101])
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1]), \
             patch("main.repository.contains", return_value=True), \
             patch("main.repository.upsert") as mock_upsert, \
             patch.object(m, "run_pipeline") as mock_pipe, \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        mock_pipe.assert_not_called()
        mock_upsert.assert_not_called()

    def test_logs_success_symbol(self, tmp_path, capsys):
        books_file, repo, verify = setup_files(tmp_path, [101])
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert"), \
             patch.object(m, "run_pipeline", return_value=FAKE_OK), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        assert "✓ Test Book — Ch 1" in capsys.readouterr().out

    def test_logs_no_disclaimer_symbol(self, tmp_path, capsys):
        books_file, repo, verify = setup_files(tmp_path, [101])
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert"), \
             patch.object(m, "run_pipeline", return_value=FAKE_NO_DISC), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        assert "~ Test Book — Ch 1 (no disclaimer)" in capsys.readouterr().out

    def test_logs_failure_symbol(self, tmp_path, capsys):
        books_file, repo, verify = setup_files(tmp_path, [101])
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert"), \
             patch.object(m, "run_pipeline", side_effect=AnchorWordNotFoundError("bad")), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        assert "✗ Test Book — Ch 1 — bad" in capsys.readouterr().out

    def test_single_failure_does_not_stop_batch(self, tmp_path, capsys):
        books_file, repo, verify = setup_files(tmp_path, [101])
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1, CH2]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert") as mock_upsert, \
             patch.object(m, "run_pipeline",
                          side_effect=[AnchorWordNotFoundError("bad"), FAKE_OK]), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        out = capsys.readouterr().out
        assert "✗ Test Book — Ch 1" in out
        assert "✓ Test Book — Ch 2" in out
        mock_upsert.assert_called_once()

    def test_failed_chapters_not_written_to_repository(self, tmp_path):
        books_file, repo, verify = setup_files(tmp_path, [101])
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert") as mock_upsert, \
             patch.object(m, "run_pipeline",
                          side_effect=BoundaryDetectionError("bad JSON")), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        mock_upsert.assert_not_called()

    def test_prints_summary(self, tmp_path, capsys):
        books_file, repo, verify = setup_files(tmp_path, [101])
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1, CH2, CH3]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert"), \
             patch.object(m, "run_pipeline",
                          side_effect=[FAKE_OK, FAKE_NO_DISC,
                                       AnchorWordNotFoundError("oops")]), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        out = capsys.readouterr().out
        assert "3 processed" in out
        assert "1 succeeded" in out
        assert "1 no-disclaimer" in out
        assert "1 failed" in out

    def test_summary_lists_failed_chapters(self, tmp_path, capsys):
        books_file, repo, verify = setup_files(tmp_path, [101])
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert"), \
             patch.object(m, "run_pipeline",
                          side_effect=AnchorWordNotFoundError("anchor missing")), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        out = capsys.readouterr().out
        assert "Ch 1" in out
        assert "anchor missing" in out

    def test_writes_chapters_to_verify_json(self, tmp_path):
        books_file, repo, verify = setup_files(tmp_path, [101])
        # ch1 succeeds, ch2 fails → only ch1 in manifest
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1, CH2]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert"), \
             patch.object(m, "run_pipeline",
                          side_effect=[FAKE_OK, AnchorWordNotFoundError("x")]), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        data = json.loads(verify.read_text())
        assert data == [CH1["listen_url"]]

    def test_upsert_payload_shape(self, tmp_path):
        """Upsert receives a dict with book_metadata and chapter keys."""
        books_file, repo, verify = setup_files(tmp_path, [101])
        with patch.object(m, "fetch_book_info", return_value=BOOK_INFO), \
             patch.object(m, "fetch_chapters", return_value=[CH1]), \
             patch("main.repository.contains", return_value=False), \
             patch("main.repository.upsert") as mock_upsert, \
             patch.object(m, "run_pipeline", return_value=FAKE_OK), \
             patch("main.AudioFetcher.fetch", new=fake_fetch):
            m.main(books_file, repo, verify)
        payload = mock_upsert.call_args[0][0]
        assert "book_metadata" in payload
        assert "chapter" in payload
        assert payload["book_metadata"]["librivox_project_id"] == 101
        assert payload["chapter"]["listen_url"] == CH1["listen_url"]
