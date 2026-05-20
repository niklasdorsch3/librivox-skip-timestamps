"""Tests for audio_fetcher.py — no real network required."""

import os
from unittest.mock import MagicMock

import pytest
import requests

from audio_fetcher import AudioFetchError, AudioFetcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_response(content: bytes = b"audio data") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.iter_content.return_value = [content]
    return resp


def _ok_session(content: bytes = b"audio data") -> MagicMock:
    session = MagicMock()
    session.get.return_value = _ok_response(content)
    return session


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_yields_valid_file_path_on_success():
    session = _ok_session()
    with AudioFetcher.fetch("http://example.com/audio.mp3", session=session) as path:
        assert os.path.exists(path)
        assert os.path.isfile(path)


def test_downloaded_content_is_written_to_file():
    content = b"fake audio bytes"
    session = _ok_session(content)
    with AudioFetcher.fetch("http://example.com/audio.mp3", session=session) as path:
        with open(path, "rb") as f:
            assert f.read() == content


def test_temp_file_deleted_after_successful_exit():
    session = _ok_session()
    with AudioFetcher.fetch("http://example.com/audio.mp3", session=session) as path:
        tmp_path = path
    assert not os.path.exists(tmp_path)


def test_temp_file_deleted_after_exception_in_with_block():
    session = _ok_session()
    tmp_path = None
    with pytest.raises(RuntimeError):
        with AudioFetcher.fetch("http://example.com/audio.mp3", session=session) as path:
            tmp_path = path
            raise RuntimeError("simulated caller error")
    assert tmp_path is not None
    assert not os.path.exists(tmp_path)


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


def test_failed_download_raises_audio_fetch_error():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.ConnectionError("no route to host")
    with pytest.raises(AudioFetchError):
        with AudioFetcher.fetch("http://example.com/audio.mp3", session=session):
            pass  # should never reach here


def test_no_temp_file_left_after_failed_download():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.ConnectionError("failed")
    leaked = []
    try:
        with AudioFetcher.fetch("http://example.com/audio.mp3", session=session) as path:
            leaked.append(path)
    except AudioFetchError:
        pass
    # temp file created internally must be gone even though we never yielded
    for p in leaked:
        assert not os.path.exists(p)


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------


def test_retries_once_on_transient_error_then_succeeds():
    content = b"audio"
    session = MagicMock()
    session.get.side_effect = [
        requests.exceptions.Timeout("timed out"),
        _ok_response(content),
    ]
    with AudioFetcher.fetch("http://example.com/audio.mp3", session=session) as path:
        with open(path, "rb") as f:
            assert f.read() == content
    assert session.get.call_count == 2


def test_raises_audio_fetch_error_after_all_retries_exhausted():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.Timeout("always times out")
    with pytest.raises(AudioFetchError):
        with AudioFetcher.fetch("http://example.com/audio.mp3", session=session):
            pass
    assert session.get.call_count == 2  # initial + 1 retry


def test_http_error_triggers_retry():
    """A 4xx/5xx response should count as a transient error and be retried."""
    bad_resp = MagicMock()
    bad_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("503")
    session = MagicMock()
    session.get.side_effect = [
        bad_resp,
        _ok_response(b"data"),
    ]
    with AudioFetcher.fetch("http://example.com/audio.mp3", session=session) as path:
        assert os.path.exists(path)
    assert session.get.call_count == 2
