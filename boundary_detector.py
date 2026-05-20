"""Boundary detector — identifies where the LibriVox Disclaimer ends in a transcript."""

import json
import os
from dataclasses import dataclass
from typing import Union

import requests

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"

_SYSTEM_PROMPT = (
    "You are analyzing a LibriVox audiobook transcript. LibriVox chapters often begin "
    "with a spoken legal disclaimer. Identify the last word of that disclaimer section.\n\n"
    "Respond ONLY with a JSON object in this exact format:\n"
    '{"disclaimer_end_word": "lastword", "confidence_score": 0.95}\n\n'
    "If there is no disclaimer present, respond with:\n"
    '{"disclaimer_end_word": null, "confidence_score": 1.0}'
)


@dataclass
class NoDisclaimer:
    """LLM determined the transcript contains no Disclaimer."""


@dataclass
class AnchorWord:
    """LLM identified the last word of the Disclaimer."""

    word: str
    confidence: float


BoundaryResult = Union[NoDisclaimer, AnchorWord]


class BoundaryDetectionError(Exception):
    """Raised when the LLM returns malformed JSON on both the initial call and the retry."""


def detect_boundary(
    transcript: str,
    session: requests.Session | None = None,
) -> BoundaryResult:
    """Return where the Disclaimer ends, or NoDisclaimer if none is present.

    Retries the Ollama call once on malformed JSON.  Raises BoundaryDetectionError
    if both attempts fail.
    """
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
    if session is None:
        session = requests.Session()

    raw = _call_ollama(transcript, model, session)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw = _call_ollama(transcript, model, session)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise BoundaryDetectionError(
                "LLM returned malformed JSON after retry"
            )

    return _parse(data)


def _call_ollama(transcript: str, model: str, session: requests.Session) -> str:
    """POST to Ollama /api/chat and return the raw content string from the reply."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        "format": "json",
        "stream": False,
    }
    resp = session.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _parse(data: dict) -> BoundaryResult:
    word = data.get("disclaimer_end_word")
    confidence = float(data.get("confidence_score", 1.0))
    if word is None:
        return NoDisclaimer()
    return AnchorWord(word=word, confidence=confidence)
