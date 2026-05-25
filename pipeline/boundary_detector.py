"""Boundary detector — identifies where the LibriVox Disclaimer ends in a transcript."""

import json
import os
from dataclasses import dataclass
from typing import Union

import requests

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"

DEFAULT_OPENAI_API_BASE = "https://api.groq.com/openai/v1"
DEFAULT_OPENAI_MODEL = "llama-3.1-8b-instant"

_SYSTEM_PROMPT = (
    "You are analyzing a LibriVox audiobook transcript. LibriVox chapters begin with a "
    "standard spoken disclaimer that follows this pattern:\n"
    "  'This is a LibriVox recording. All LibriVox recordings are in the public domain. "
    "For more information, please visit LibriVox.org. "
    "[Title] by [Author], [chapter info], read by [Reader Name].'\n\n"
    "The disclaimer ALWAYS ends with 'read by [Reader Name].' — the reader's name is the "
    "very last word. It does NOT include the chapter heading (e.g. 'Chapter 1') or any "
    "book text.\n\n"
    "IMPORTANT RULES:\n"
    "1. When the phrase 'read by [Name]' appears, the anchor word is ALWAYS the reader's "
    "last name (or the final word of their name). Never return 'org', 'domain', or any "
    "other word if a reader name is present.\n"
    "2. Only return 'org' or 'domain' if there is NO 'read by [Name]' phrase anywhere in "
    "the transcript.\n\n"
    "Example — single chapter:\n"
    "  Transcript: '...please visit LibriVox.org. Pride and Prejudice by Jane Austen. "
    "Chapter 1. Read by Mary Jones.'\n"
    "  Correct response: {\"disclaimer_end_word\": \"Jones\", \"confidence_score\": 0.99}\n\n"
    "Example — multi-chapter file:\n"
    "  Transcript: '...please visit LibriVox.org. Pride and Prejudice by Jane Austen. "
    "Chapters 4 and 5. Read by Mary Jones.'\n"
    "  Correct response: {\"disclaimer_end_word\": \"Jones\", \"confidence_score\": 0.99}\n\n"
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

    Uses an OpenAI-compatible API (e.g. Groq) when OPENAI_API_KEY is set,
    otherwise falls back to a local Ollama instance.

    Retries once on malformed JSON. Raises BoundaryDetectionError if both
    attempts fail.
    """
    if session is None:
        session = requests.Session()

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        caller = lambda t: _call_openai(t, session, api_key)
    else:
        model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        caller = lambda t: _call_ollama(t, model, session)

    raw = caller(transcript)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw = caller(transcript)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise BoundaryDetectionError(
                "LLM returned malformed JSON after retry"
            )

    return _parse(data)


def _call_openai(transcript: str, session: requests.Session, api_key: str) -> str:
    """POST to an OpenAI-compatible /v1/chat/completions endpoint and return content."""
    api_base = os.environ.get("OPENAI_API_BASE", DEFAULT_OPENAI_API_BASE)
    model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = session.post(
        f"{api_base}/chat/completions",
        json=payload,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


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
