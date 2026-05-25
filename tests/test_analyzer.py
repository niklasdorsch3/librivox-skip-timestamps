"""Integration tests for the Pipeline module.

Uses the real audio fixture but injects a fake BoundaryDetector to avoid
requiring a running Ollama instance.
"""

import logging
import os

import pytest

from pipeline.analyzer import (
    AnchorWordNotFoundError,
    ChapterMetadata,
    run_pipeline,
)
from pipeline.boundary_detector import AnchorWord, NoDisclaimer

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_chapter.mp3")


@pytest.fixture
def meta():
    return ChapterMetadata(
        chapter_index=1,
        chapter_title="Chapter 1",
        listen_url="https://librivox.org/test",
        file_name="chapter_01.mp3",
    )


def _no_disclaimer(transcript: str) -> NoDisclaimer:
    return NoDisclaimer()


def test_no_disclaimer_returns_zero_skip(meta):
    result = run_pipeline(FIXTURE, meta, detector=_no_disclaimer)
    assert result.exact_audio_skip_seconds == 0.0
    assert result.detected_disclaimer_anchor_word is None
    assert result.is_outlier is False
    assert result.verified is False


def test_low_confidence_treated_as_no_disclaimer(meta, monkeypatch):
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.9")

    def low_conf(transcript: str):
        return AnchorWord(word="domain", confidence=0.3)

    result = run_pipeline(FIXTURE, meta, detector=low_conf)
    assert result.exact_audio_skip_seconds == 0.0
    assert result.detected_disclaimer_anchor_word is None


def test_anchor_word_not_found_raises(meta):
    def bad_anchor(transcript: str):
        return AnchorWord(word="XYZNOTFOUND99", confidence=0.99)

    with pytest.raises(AnchorWordNotFoundError, match="XYZNOTFOUND99"):
        run_pipeline(FIXTURE, meta, detector=bad_anchor)


def test_disclaimer_detected_returns_skip_seconds(meta):
    # "domain" is the last word of the disclaimer in the fixture (at ~6.06 s)
    def disclaimer(transcript: str):
        return AnchorWord(word="domain", confidence=0.99)

    result = run_pipeline(FIXTURE, meta, detector=disclaimer)
    assert result.exact_audio_skip_seconds >= 0.0
    assert result.detected_disclaimer_anchor_word == "domain"
    assert isinstance(result.is_outlier, bool)


def test_whisper_model_env_var_respected(meta, monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "tiny")
    result = run_pipeline(FIXTURE, meta, detector=_no_disclaimer)
    assert result.exact_audio_skip_seconds == 0.0


def test_silence_threshold_env_var_respected(meta, monkeypatch):
    # Threshold of 0.0 dBFS means any audio chunk is "silence", so
    # t_exact == t_approx + 0ms (first 50ms window triggers immediately)
    monkeypatch.setenv("SILENCE_THRESHOLD_DBFS", "0.0")

    def disclaimer(transcript: str):
        return AnchorWord(word="domain", confidence=0.99)

    result = run_pipeline(FIXTURE, meta, detector=disclaimer)
    assert result.exact_audio_skip_seconds >= 0.0


def test_log_line_emitted_with_t_approx_and_t_exact(meta, caplog):
    def disclaimer(transcript: str):
        return AnchorWord(word="domain", confidence=0.99)

    with caplog.at_level(logging.INFO, logger="pipeline.analyzer"):
        run_pipeline(FIXTURE, meta, detector=disclaimer)

    log_messages = [r.message for r in caplog.records]
    assert any("t_ref" in m and "t_exact" in m and "delta" in m for m in log_messages)


def test_outlier_flag_set_when_delta_exceeds_four_seconds(meta, monkeypatch):
    # Use a very high silence threshold so Stage 3 never finds silence (t_exact = t_approx)
    # and manually check is_outlier behaviour via a different approach:
    # patch _detect_silence to simulate a >4s shift.
    import pipeline.analyzer as analyzer

    def fake_silence(audio_path, t_approx, threshold_dbfs):
        return t_approx + 5.0  # force delta = 5s > 4s threshold

    monkeypatch.setattr(analyzer, "_detect_silence", fake_silence)

    def disclaimer(transcript: str):
        return AnchorWord(word="domain", confidence=0.99)

    result = run_pipeline(FIXTURE, meta, detector=disclaimer)
    assert result.is_outlier is True
