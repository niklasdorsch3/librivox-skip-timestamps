"""Pipeline — runs Transcription, Boundary Analysis and Silence Detection stages."""

import logging
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional

from faster_whisper import WhisperModel
from pydub import AudioSegment

from boundary_detector import AnchorWord, BoundaryResult, NoDisclaimer, detect_boundary

logger = logging.getLogger(__name__)

_DEFAULT_WHISPER_MODEL = "base"
_DEFAULT_SILENCE_THRESHOLD_DBFS = -45.0
_DEFAULT_CONFIDENCE_THRESHOLD = 0.5
_MAX_AUDIO_SECONDS = 45
_SILENCE_WINDOW_MS = 3000
_SILENCE_STEP_MS = 50
_OUTLIER_DELTA_SECONDS = 4.0
_CHAPTER_HEADING_WINDOW_SECONDS = 8.0
_MIN_SILENCE_DURATION_MS = 300  # ignore sub-word dips shorter than this
_GAP_SILENCE_THRESHOLD_DBFS = -38.0  # looser threshold for inter-segment gap detection
_CHAPTER_HEADING_PATTERN = re.compile(r"^(chapter|part|book|prologue|epilogue|preface|introduction)$")

TokenMap = list[tuple[str, float]]
DetectorFn = Callable[[str], BoundaryResult]


@dataclass
class ChapterMetadata:
    chapter_index: int
    chapter_title: str
    listen_url: str
    file_name: str


@dataclass
class PipelineResult:
    exact_audio_skip_seconds: float
    detected_disclaimer_anchor_word: Optional[str]
    is_outlier: bool
    verified: bool = False


class AnchorWordNotFoundError(Exception):
    """Raised when the Anchor Word cannot be found in the Token Map."""


def run_pipeline(
    audio_path: str,
    chapter_metadata: ChapterMetadata,
    detector: DetectorFn | None = None,
) -> PipelineResult:
    """Run Transcription, Boundary Analysis and Silence Detection; return a PipelineResult."""
    whisper_model = os.environ.get("WHISPER_MODEL", _DEFAULT_WHISPER_MODEL)
    silence_threshold = float(
        os.environ.get("SILENCE_THRESHOLD_DBFS", str(_DEFAULT_SILENCE_THRESHOLD_DBFS))
    )
    confidence_threshold = float(
        os.environ.get("CONFIDENCE_THRESHOLD", str(_DEFAULT_CONFIDENCE_THRESHOLD))
    )
    if detector is None:
        detector = detect_boundary

    # Stage 1: Transcription
    token_map = _transcribe(audio_path, whisper_model)
    transcript = " ".join(word for word, _ in token_map)

    # Stage 2: Boundary Analysis
    boundary = detector(transcript)

    if isinstance(boundary, NoDisclaimer) or (
        isinstance(boundary, AnchorWord) and boundary.confidence < confidence_threshold
    ):
        return PipelineResult(
            exact_audio_skip_seconds=0.0,
            detected_disclaimer_anchor_word=None,
            is_outlier=False,
        )

    # AnchorWord with sufficient confidence — look up in token map
    anchor_key = _normalize(boundary.word)
    t_approx: float | None = None
    for word, end_time in token_map:
        if _normalize(word) == anchor_key:
            t_approx = end_time

    if t_approx is None:
        raise AnchorWordNotFoundError(
            f"Anchor word '{boundary.word}' not found in Token Map"
        )

    # Stage 2b: if a chapter heading follows, find where audio resumes in the gap
    t_chapter_end = _find_chapter_heading_end(token_map, t_approx)
    if t_chapter_end is not None:
        t_exact = _detect_silence_before(audio_path, t_approx, t_chapter_end, _GAP_SILENCE_THRESHOLD_DBFS)
    else:
        t_exact = _detect_silence(audio_path, t_approx, silence_threshold)

    t_ref = t_chapter_end if t_chapter_end is not None else t_approx
    delta = t_exact - t_ref
    is_outlier = bool(abs(delta) > _OUTLIER_DELTA_SECONDS)
    outlier_tag = " [OUTLIER]" if is_outlier else ""
    logger.info(
        "t_ref: %.2fs  t_exact: %.2fs  delta: %+.2fs%s",
        t_ref,
        t_exact,
        delta,
        outlier_tag,
    )

    return PipelineResult(
        exact_audio_skip_seconds=t_exact,
        detected_disclaimer_anchor_word=boundary.word,
        is_outlier=is_outlier,
    )


def _normalize(word: str) -> str:
    """Strip punctuation and lowercase for anchor word matching."""
    return re.sub(r"[^a-z0-9]+", "", word.lower())


def _transcribe(audio_path: str, model_name: str) -> TokenMap:
    """Trim to 45 s, transcribe with faster-whisper, return token map."""
    audio = AudioSegment.from_file(audio_path)
    trimmed = audio[: _MAX_AUDIO_SECONDS * 1000]

    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        trimmed.export(tmp_path, format="mp3")
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(tmp_path, word_timestamps=True)
        token_map: TokenMap = []
        for segment in segments:
            if segment.words:
                for word in segment.words:
                    token_map.append((word.word.strip(), float(word.end)))
        return token_map
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _find_chapter_heading_end(token_map: TokenMap, t_approx: float) -> float | None:
    """Return the end time of the chapter heading keyword (e.g. 'Chapter', 'Part') if
    one appears within _CHAPTER_HEADING_WINDOW_SECONDS after t_approx, else None."""
    deadline = t_approx + _CHAPTER_HEADING_WINDOW_SECONDS
    i = 0
    while i < len(token_map) and token_map[i][1] <= t_approx:
        i += 1
    while i < len(token_map) and token_map[i][1] <= deadline:
        word, end_time = token_map[i]
        if _CHAPTER_HEADING_PATTERN.match(_normalize(word)):
            logger.info("Chapter heading '%s' found at %.2fs", word.strip(), end_time)
            return end_time
        i += 1
    return None


def _detect_silence_before(
    audio_path: str,
    t_gap_start: float,
    t_gap_end: float,
    threshold_dbfs: float,
) -> float:
    """Return the point where audio resumes in the gap between t_gap_start and t_gap_end.

    Scans forward from t_gap_start (end of disclaimer anchor) to t_gap_end
    (end of chapter heading word).  Finds the last silence→audio transition
    that is preceded by at least _MIN_SILENCE_DURATION_MS of silence,
    i.e. where the chapter heading starts speaking.
    """
    audio = AudioSegment.from_file(audio_path)
    start_ms = int(t_gap_start * 1000)
    end_ms = int(t_gap_end * 1000)

    in_silence = False
    silence_start_ms: int | None = None
    last_audio_onset: int | None = None
    for i in range(start_ms, end_ms, _SILENCE_STEP_MS):
        chunk = audio[i : i + _SILENCE_STEP_MS]
        is_silent = chunk.dBFS < threshold_dbfs
        if not in_silence and is_silent:
            in_silence = True
            silence_start_ms = i
        elif in_silence and not is_silent:
            duration = i - (silence_start_ms or i)
            if duration >= _MIN_SILENCE_DURATION_MS:
                last_audio_onset = i  # substantial gap — keep scanning for the last one
            in_silence = False
            silence_start_ms = None

    if last_audio_onset is not None:
        return last_audio_onset / 1000.0
    return t_gap_end


def _detect_silence(audio_path: str, t_approx: float, threshold_dbfs: float) -> float:
    """Scan 3 s window from t_approx in 50 ms steps; return first silence onset."""
    audio = AudioSegment.from_file(audio_path)
    start_ms = int(t_approx * 1000)
    end_ms = min(start_ms + _SILENCE_WINDOW_MS, len(audio))
    window = audio[start_ms:end_ms]

    for i in range(0, len(window) - _SILENCE_STEP_MS + 1, _SILENCE_STEP_MS):
        chunk = window[i : i + _SILENCE_STEP_MS]
        if chunk.dBFS < threshold_dbfs:
            return t_approx + (i / 1000.0)

    return t_approx
