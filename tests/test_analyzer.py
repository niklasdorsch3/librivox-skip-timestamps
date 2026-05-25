"""Integration tests for the Pipeline module.

Uses the real audio fixture but injects a fake BoundaryDetector to avoid
requiring a running Ollama instance.
"""

import logging
import os
import re

import pytest

from pipeline.analyzer import (
    AnchorWordNotFoundError,
    ChapterMetadata,
    _find_chapter_heading_end,
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


def _last_index_of(word: str, transcript: str) -> int:
    """Return the last token index for *word* in an indexed transcript '[0]w1 [1]w2 ...'"""
    matches = [int(m.group(1)) for m in re.finditer(rf"\[(\d+)\]{re.escape(word)}", transcript)]
    if not matches:
        raise ValueError(f"'{word}' not found in indexed transcript")
    return matches[-1]


def test_no_disclaimer_returns_zero_skip(meta):
    result = run_pipeline(FIXTURE, meta, detector=_no_disclaimer)
    assert result.exact_audio_skip_seconds == 0.0
    assert result.detected_disclaimer_anchor_word is None
    assert result.is_outlier is False
    assert result.verified is False


def test_low_confidence_treated_as_no_disclaimer(meta, monkeypatch):
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.9")

    def low_conf(transcript: str):
        return AnchorWord(index=0, confidence=0.3)

    result = run_pipeline(FIXTURE, meta, detector=low_conf)
    assert result.exact_audio_skip_seconds == 0.0
    assert result.detected_disclaimer_anchor_word is None


def test_anchor_word_not_found_raises(meta):
    def bad_anchor(transcript: str):
        return AnchorWord(index=9999, confidence=0.99)

    with pytest.raises(AnchorWordNotFoundError, match="9999"):
        run_pipeline(FIXTURE, meta, detector=bad_anchor)


def test_disclaimer_detected_returns_skip_seconds(meta):
    # "domain" is the last word of the disclaimer in the fixture (at ~6.06 s)
    def disclaimer(transcript: str):
        return AnchorWord(index=_last_index_of("domain", transcript), confidence=0.99)

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
        return AnchorWord(index=_last_index_of("domain", transcript), confidence=0.99)

    result = run_pipeline(FIXTURE, meta, detector=disclaimer)
    assert result.exact_audio_skip_seconds >= 0.0


def test_log_line_emitted_with_t_approx_and_t_exact(meta, caplog):
    def disclaimer(transcript: str):
        return AnchorWord(index=_last_index_of("domain", transcript), confidence=0.99)

    with caplog.at_level(logging.INFO, logger="pipeline.analyzer"):
        run_pipeline(FIXTURE, meta, detector=disclaimer)

    log_messages = [r.message for r in caplog.records]
    assert any("t_ref" in m and "t_exact" in m and "delta" in m for m in log_messages)


# ---------------------------------------------------------------------------
# _find_chapter_heading_end unit tests
# ---------------------------------------------------------------------------


def test_find_chapter_heading_end_returns_none_when_no_heading():
    token_map = [("This", 0.5), ("is", 0.8), ("text", 1.2)]
    assert _find_chapter_heading_end(token_map, 0.0) is None


def test_find_chapter_heading_end_returns_heading_within_window():
    token_map = [("domain", 5.0), ("Chapter", 8.0), ("one", 8.5)]
    result = _find_chapter_heading_end(token_map, 5.0)
    assert result == pytest.approx(8.0)


def test_find_chapter_heading_end_returns_none_when_heading_outside_window():
    token_map = [("domain", 5.0), ("Chapter", 20.0), ("one", 20.5)]
    assert _find_chapter_heading_end(token_map, 5.0) is None


def test_find_chapter_heading_end_returns_last_match_for_multi_chapter():
    # "Chapter 4 and 5. Chapter 4." — must return the LAST "Chapter", not the first.
    token_map = [
        ("domain", 10.0),
        ("Chapter", 12.0), ("4", 12.3), ("and", 12.5), ("5", 12.7),
        ("Chapter", 15.0), ("4", 15.3),
    ]
    result = _find_chapter_heading_end(token_map, 10.0)
    assert result == pytest.approx(15.0)


def test_find_chapter_heading_end_single_heading_unchanged():
    token_map = [("domain", 10.0), ("Chapter", 14.0), ("one", 14.4)]
    result = _find_chapter_heading_end(token_map, 10.0)
    assert result == pytest.approx(14.0)


def test_find_chapter_heading_end_matches_various_keywords():
    for keyword in ("Part", "Book", "Prologue", "Epilogue", "Preface", "Introduction"):
        token_map = [("domain", 5.0), (keyword, 8.0)]
        result = _find_chapter_heading_end(token_map, 5.0)
        assert result == pytest.approx(8.0), f"Expected match for keyword '{keyword}'"


def test_outlier_flag_set_when_delta_exceeds_four_seconds(meta, monkeypatch):
    import pipeline.analyzer as analyzer

    def fake_silence(audio_path, t_approx, threshold_dbfs):
        return t_approx + 5.0  # force delta = 5s > 4s threshold

    monkeypatch.setattr(analyzer, "_detect_silence", fake_silence)

    def disclaimer(transcript: str):
        return AnchorWord(index=_last_index_of("domain", transcript), confidence=0.99)

    result = run_pipeline(FIXTURE, meta, detector=disclaimer)
    assert result.is_outlier is True
