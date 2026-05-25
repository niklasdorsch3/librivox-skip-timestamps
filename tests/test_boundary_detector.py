"""Tests for boundary_detector.py — no running Ollama or API key required."""

import json
import os
from unittest.mock import MagicMock

import pytest

from pipeline.boundary_detector import (
    AnchorWord,
    BoundaryDetectionError,
    NoDisclaimer,
    detect_boundary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_ollama_response(content: str) -> MagicMock:
    """Build a mock that looks like a requests.Response wrapping an Ollama reply."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"message": {"content": content}}
    return resp


def _fake_openai_response(content: str) -> MagicMock:
    """Build a mock that looks like an OpenAI-compatible response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def _payload(word: str | None, confidence: float = 0.95) -> str:
    return json.dumps({"disclaimer_end_word": word, "confidence_score": confidence})


def _fake_ollama_session(*contents: str) -> MagicMock:
    session = MagicMock()
    session.post.side_effect = [_fake_ollama_response(c) for c in contents]
    return session


def _fake_openai_session(*contents: str) -> MagicMock:
    session = MagicMock()
    session.post.side_effect = [_fake_openai_response(c) for c in contents]
    return session


# ---------------------------------------------------------------------------
# Ollama happy-path tests
# ---------------------------------------------------------------------------


def test_returns_anchor_word_when_llm_identifies_disclaimer(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    session = _fake_ollama_session(_payload("LibriVox", 0.98))
    result = detect_boundary("This is a LibriVox recording ...", session=session)
    assert isinstance(result, AnchorWord)
    assert result.word == "LibriVox"
    assert result.confidence == pytest.approx(0.98)


def test_returns_no_disclaimer_when_llm_returns_null(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    session = _fake_ollama_session(_payload(None, 1.0))
    result = detect_boundary("Chapter one. It was a dark...", session=session)
    assert isinstance(result, NoDisclaimer)


# ---------------------------------------------------------------------------
# Retry logic tests
# ---------------------------------------------------------------------------


def test_malformed_json_on_first_attempt_triggers_exactly_one_retry(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    session = _fake_ollama_session("NOT JSON", _payload("recording", 0.9))
    result = detect_boundary("transcript", session=session)
    assert isinstance(result, AnchorWord)
    assert session.post.call_count == 2


def test_malformed_json_on_both_attempts_raises_boundary_detection_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    session = _fake_ollama_session("NOT JSON", "{also bad")
    with pytest.raises(BoundaryDetectionError):
        detect_boundary("transcript", session=session)
    assert session.post.call_count == 2


# ---------------------------------------------------------------------------
# Ollama environment variable tests
# ---------------------------------------------------------------------------


def test_ollama_model_env_var_controls_model_used(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "gemma2:2b")
    session = _fake_ollama_session(_payload("word", 0.8))
    detect_boundary("transcript", session=session)
    _, kwargs = session.post.call_args
    assert kwargs["json"]["model"] == "gemma2:2b"


def test_default_ollama_model_used_when_env_var_absent(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    session = _fake_ollama_session(_payload("word", 0.8))
    detect_boundary("transcript", session=session)
    _, kwargs = session.post.call_args
    assert kwargs["json"]["model"] == "llama3.2:3b"


# ---------------------------------------------------------------------------
# OpenAI-compatible (Groq) path tests
# ---------------------------------------------------------------------------


def test_openai_path_used_when_api_key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    session = _fake_openai_session(_payload("LibriVox", 0.95))
    result = detect_boundary("transcript", session=session)
    assert isinstance(result, AnchorWord)
    assert result.word == "LibriVox"


def test_openai_path_sends_bearer_auth(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "my-secret-key")
    session = _fake_openai_session(_payload("word", 0.9))
    detect_boundary("transcript", session=session)
    _, kwargs = session.post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer my-secret-key"


def test_openai_path_uses_default_groq_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    session = _fake_openai_session(_payload("word", 0.9))
    detect_boundary("transcript", session=session)
    url, _ = session.post.call_args[0], session.post.call_args[1]
    assert "groq.com" in session.post.call_args[0][0]


def test_openai_path_uses_custom_api_base(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
    session = _fake_openai_session(_payload("word", 0.9))
    detect_boundary("transcript", session=session)
    assert "openrouter.ai" in session.post.call_args[0][0]


def test_openai_path_uses_default_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    session = _fake_openai_session(_payload("word", 0.9))
    detect_boundary("transcript", session=session)
    _, kwargs = session.post.call_args
    assert kwargs["json"]["model"] == "llama-3.1-8b-instant"


def test_openai_path_uses_custom_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "mixtral-8x7b-32768")
    session = _fake_openai_session(_payload("word", 0.9))
    detect_boundary("transcript", session=session)
    _, kwargs = session.post.call_args
    assert kwargs["json"]["model"] == "mixtral-8x7b-32768"


def test_openai_retry_on_malformed_json(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    session = _fake_openai_session("NOT JSON", _payload("word", 0.9))
    result = detect_boundary("transcript", session=session)
    assert isinstance(result, AnchorWord)
    assert session.post.call_count == 2
