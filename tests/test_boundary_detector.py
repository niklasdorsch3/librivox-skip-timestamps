"""Tests for boundary_detector.py — no running Ollama required."""

import json
import os
from unittest.mock import MagicMock

import pytest

from boundary_detector import (
    AnchorWord,
    BoundaryDetectionError,
    NoDisclaimer,
    detect_boundary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(content: str) -> MagicMock:
    """Build a mock that looks like a requests.Response wrapping an Ollama reply."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"message": {"content": content}}
    return resp


def _ollama_payload(word: str | None, confidence: float = 0.95) -> str:
    return json.dumps({"disclaimer_end_word": word, "confidence_score": confidence})


def _fake_session(*contents: str) -> MagicMock:
    """Return a mock session whose .post() yields successive responses."""
    session = MagicMock()
    session.post.side_effect = [_fake_response(c) for c in contents]
    return session


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_returns_anchor_word_when_llm_identifies_disclaimer():
    session = _fake_session(_ollama_payload("LibriVox", 0.98))
    result = detect_boundary("This is a LibriVox recording ...", session=session)
    assert isinstance(result, AnchorWord)
    assert result.word == "LibriVox"
    assert result.confidence == pytest.approx(0.98)


def test_returns_no_disclaimer_when_llm_returns_null():
    session = _fake_session(_ollama_payload(None, 1.0))
    result = detect_boundary("Chapter one. It was a dark...", session=session)
    assert isinstance(result, NoDisclaimer)


# ---------------------------------------------------------------------------
# Retry logic tests
# ---------------------------------------------------------------------------


def test_malformed_json_on_first_attempt_triggers_exactly_one_retry():
    valid = _ollama_payload("recording", 0.9)
    session = _fake_session("NOT JSON", valid)
    result = detect_boundary("transcript", session=session)
    assert isinstance(result, AnchorWord)
    assert session.post.call_count == 2


def test_malformed_json_on_both_attempts_raises_boundary_detection_error():
    session = _fake_session("NOT JSON", "{also bad")
    with pytest.raises(BoundaryDetectionError):
        detect_boundary("transcript", session=session)
    assert session.post.call_count == 2


# ---------------------------------------------------------------------------
# Environment variable test
# ---------------------------------------------------------------------------


def test_ollama_model_env_var_controls_model_used(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "gemma2:2b")
    session = _fake_session(_ollama_payload("word", 0.8))
    detect_boundary("transcript", session=session)
    _, kwargs = session.post.call_args
    assert kwargs["json"]["model"] == "gemma2:2b"


def test_default_model_used_when_env_var_absent(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    session = _fake_session(_ollama_payload("word", 0.8))
    detect_boundary("transcript", session=session)
    _, kwargs = session.post.call_args
    assert kwargs["json"]["model"] == "llama3.2:3b"
