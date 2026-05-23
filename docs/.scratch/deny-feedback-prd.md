# PRD: Deny Feedback — Closing the Pipeline Improvement Loop

Status: in-progress

## Problem Statement

The verify UI currently offers a binary approve/deny signal. A denial tells us the pipeline was wrong, but captures nothing about *how* or *why*. Without structured failure data, the same class of mistake repeats indefinitely across runs and contributors cannot identify which pipeline parameter to tune.

## Solution

Intercept the deny action with a modal that captures:
- The correct skip timestamp (human listens from start, types it in)
- A reason category that maps 1:1 to a specific pipeline lever
- Optional free-text notes

Feedback is stored inline in `chapters_to_verify.json` on the denied entry. No separate file. Contributors can then feed the file to Claude Code for analysis and receive concrete tuning suggestions (e.g. "raise `SILENCE_THRESHOLD_DBFS` to -40").

## Pipeline Levers

| Stage | Lever | Env Var / Constant |
|-------|-------|--------------------|
| 1 — Transcription | Whisper model size | `WHISPER_MODEL` (default: `base`) |
| 2 — Boundary Analysis | LLM model | `OLLAMA_MODEL` / `OPENAI_MODEL` |
| 2 — Boundary Analysis | Confidence cutoff | `CONFIDENCE_THRESHOLD` (default: `0.5`) |
| 3 — Silence Detection | dBFS threshold | `SILENCE_THRESHOLD_DBFS` (default: `-45.0`) |
| 3 — Silence Detection | Scan window | `_SILENCE_WINDOW_MS = 3000` |
| 2b — Chapter Heading | Gap threshold | `_GAP_SILENCE_THRESHOLD_DBFS = -38.0` |

## Denial Reason Categories

| Value | Human label | Lever blamed |
|-------|-------------|--------------|
| `wrong_anchor_word` | "LLM picked wrong anchor word" | `OLLAMA_MODEL / OPENAI_MODEL` |
| `false_positive` | "No disclaimer, but pipeline added a skip" | `CONFIDENCE_THRESHOLD` |
| `false_negative` | "Disclaimer exists but pipeline returned 0s" | `CONFIDENCE_THRESHOLD` |
| `silence_detection` | "Anchor correct, but silence position is off" | `SILENCE_THRESHOLD_DBFS` |
| `transcription_error` | "Whisper mis-transcribed, causing wrong word lookup" | `WHISPER_MODEL` |

## User Stories

1. As a contributor, I want a deny modal with audio playback controls (including "play from start"), so that I can listen from the beginning before deciding the correct timestamp.
2. As a contributor, I want to select a reason category when denying, so that my feedback is actionable rather than a binary signal.
3. As a contributor, I want the correct timestamp pre-filled with the pipeline's value, so that I only need to correct it when it's wrong.
4. As a contributor, I want denied entries in `chapters_to_verify.json` to include `denial_reason`, `denial_lever`, `human_timestamp`, and `notes`, so that I can give the file to Claude Code and ask "what should I tune?".
5. As a contributor, I want the reason category to link directly to a named pipeline env var or constant, so that the feedback is concrete and not just a label.

## Output Schema (chapters_to_verify.json denied entry)

```json
{
  "listen_url": "https://...",
  "chapter_title": "Chapter 1",
  "title": "Pride and Prejudice",
  "verification_status": "denied",
  "denial_reason": "silence_detection",
  "denial_lever": "SILENCE_THRESHOLD_DBFS",
  "human_timestamp": 20.5,
  "notes": "gap was too short at -45, try -40"
}
```

## Files Changed

- `verify/ui.html` — deny modal with playback controls and form
- `verify/candidates.py` — extend `update_verification_status` with feedback params + `LEVER_MAP`
- `verify/session.py` — `deny(feedback: dict)` signature
- `verify/server.py` — parse POST body for `/api/deny`
- `verify/__main__.py` — `on_deny(url, feedback)` callback wiring

## Out of Scope

- Automated analysis tooling — contributors will use Claude Code CLI to interpret `chapters_to_verify.json`
- Changing the approve flow
- Any changes to `repository.json` schema
