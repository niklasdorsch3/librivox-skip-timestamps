# librevox-timestamps — Architecture

> For domain terminology (Pipeline, Stage, Disclaimer, Repository, etc.) see `CONTEXT.md`.
> For individual architectural decisions and their rationale see `docs/adr/`.

---

## System Overview

A local, fully offline Python pipeline that processes LibriVox audio files and produces a public JSON Repository of per-chapter skip timestamps. No external APIs are used at runtime — all inference runs locally via faster-whisper and Ollama.

This repository is a data companion to the **easy-audiobook** player. `repository.json` is a public dataset — consumers download it and serve it themselves from within their own app. It is not fetched at runtime from this repo.

```
┌─────────────────────────────────────────────────────┐
│                   Batch Runner (main.py)             │
│  reads books.txt · fetches chapters · consults Checkpoint DB │
└────────────────────────┬────────────────────────────┘
                         │ per file
                         ▼
┌─────────────────────────────────────────────────────┐
│                   Pipeline (analyzer.py)             │
│                                                      │
│  Stage 1: Transcription (faster-whisper)             │
│     └─▶ Token Map [(word, end_time_s), ...]          │
│                                                      │
│  Stage 2: Boundary Analysis (Ollama / local LLM)     │
│     └─▶ Anchor Word + Confidence Score → T_approx   │
│                                                      │
│  Stage 3: Silence Detection (pydub / ffmpeg)         │
│     └─▶ T_exact                                      │
│                                                      │
│  Stage 4: Repository Update (pydantic + JSON)        │
│     └─▶ repository.json entry written/updated        │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   repository.json    │
              │   (public artefact   │
              │    + resume state)   │
              └──────────────────────┘
```

---

## Modules

### `main.py` — Batch Runner

Entry point. Reads a flat list of LibriVox book IDs from `books.txt` (one ID per line), fetches all chapters for each book from the LibriVox API, and skips any chapter whose `listen_url` already exists in `repository.json`. Failed chapters are logged to stdout with their error reason and retried on the next run. Downloads the chapter audio to a temporary file, invokes the Pipeline, then deletes the temporary file regardless of success or failure. Audio never persists to disk beyond the duration of a single chapter's processing.

Logs to stdout per file:
- `✓ <file>` — completed successfully
- `~ <file> (no disclaimer)` — completed, no Disclaimer detected
- `✗ <file> — <reason>` — failed (e.g. "LLM returned malformed JSON after retry", "Anchor Word not found in Token Map")

At the end of each run, prints a summary: total processed, succeeded, no-disclaimer, failed. Failed files are listed by path with their error reason so they can be investigated or re-run.

### `analyzer.py` — Pipeline

Implements three Stages sequentially — Transcription, Boundary Analysis, Silence Detection. Returns a typed `PipelineResult` or raises a typed exception. Has no global state — all data flows through function arguments and return values. Has no dependency on the Repository module — `main.py` calls `repository.upsert(result)` after a successful run.

#### Stage 1 — Transcription

- Receives a path to a temporary local audio file (downloaded by the Batch Runner).
- Loads only the first 45 seconds.
- Runs `faster-whisper` locally (model: `tiny` or `base`, CPU or GPU).
- Returns a **Token Map**: `list[tuple[str, float]]` — `(word, end_time_seconds)`.

#### Stage 2 — Boundary Analysis

- Sends the full transcribed text block to a locally running Ollama instance (`http://localhost:11434/api/chat`) using JSON mode.
- Model: `gemma2:2b` or `llama3.2:3b` (pulled automatically on first run).
- Prompt instructs the model to identify the **Anchor Word** — the last word of the Disclaimer.
- Response schema: `{"disclaimer_end_word": str | null, "confidence_score": float}`. `null` means no Disclaimer detected — clean success, recorded as `exact_audio_skip_seconds: 0`.
- If the response is malformed JSON: retry once. If still malformed: the file fails, recorded in Checkpoint DB with an error message; Pipeline moves to the next file.
- If the Anchor Word cannot be located in the Token Map: the file fails, recorded in Checkpoint DB with an error; Pipeline moves to the next file.
- On success, maps the Anchor Word to its position in the Token Map to obtain **T_approx**.

#### Stage 3 — Silence Detection

- Extracts a 3-second audio window starting at T_approx using `pydub`.
- Scans in 50 ms steps, measuring dBFS.
- First step below −45 dBFS defines **T_exact**.
- If no silence is found in the window, T_exact = T_approx (and the entry is flagged).

#### Stage 4 — Repository Update

- Validates the result with a `pydantic` schema.
- Enforces safety checks: `exact_audio_skip_seconds` ≤ 45 s; Outlier flagged if |T_exact − T_approx| > 4 s.
- Upserts the chapter entry into `repository.json`.

### `verify.py` — Verification Script

Run after `main.py` completes. Picks 10 chapters at random from the new batch output and walks the contributor through each one interactively:

```
Chapter 3/10: The Art of War — Chapter 1
Listen: https://librivox.org/...
Pipeline result: 14.80s
Does this sound correct? [y/n]:
```

The contributor opens the URL, skips to 14.80s, listens, and presses `y` or `n`. On `y`, the entry is written with `"verified": true`. On `n`, a replacement chapter is picked at random until 10 are confirmed.

Once 10 entries are verified, `verify.py` exits and the output is ready to PR.

Does not re-run the Pipeline — it only marks existing output. Does not write to the Checkpoint DB.

### `.github/workflows/validate-contribution.yml` — CI check

Runs on every pull request. Executes a validation script (`validate_contribution.py`) that diffs `repository.json` against the base branch and checks:

1. No more than 100 new chapter entries in this PR
2. At least 10 of the new entries have `"verified": true`

Fails the PR if either condition is not met, with a clear error message stating which rule was violated. No other checks — does not validate timestamp values or re-run the Pipeline.

### `repository.json` — Public Output

Flat JSON file. One top-level key per LibriVox project ID. Each entry contains `book_metadata` and a `chapters` array. `gutenberg_text_id` is optional — `null` when no Project Gutenberg text exists. Written atomically (write to temp file, then rename) to avoid corruption on interruption.

Contributors write directly to `repository.json` on their fork. The PR diff is the review surface — no separate staging file.

---

## Data flow (per file)

```
chapter listen_url
  → already in repository.json? skip
  → Batch Runner downloads to temp file
  → Stage 1: faster-whisper → Token Map
  → Stage 2: Ollama → Anchor Word + T_approx (or no_disclaimer)
  → Stage 3: pydub → T_exact
  → Stage 4: pydantic → repository.json upsert
  → failure at any stage → log error, move to next chapter
```

---

## Environment & dependencies

| Dependency | Role |
|---|---|
| `faster-whisper` | Local STT — word-level transcription |
| `ollama` (CLI) | Local LLM runtime |
| `pydub` | Audio windowing and dBFS measurement |
| `ffmpeg` | System dependency required by pydub |
| `pydantic` | Schema validation for Repository output |
| `requests` | HTTP client for Ollama REST API |

**Setup:**

```bash
pip install -r requirements.txt
# verifies ffmpeg and ollama are installed, pulls model if needed
python setup.py
```

In development, set `OLLAMA_MODEL` env var to switch models without code changes. Set `WHISPER_MODEL` to switch between `tiny` and `base`.

---

## Contribution workflow

```
1. Fork the repo
2. Add LibriVox book IDs to books.txt
3. python main.py              # downloads + processes chapters, writes to repository.json
4. python verify.py            # interactively confirm 10 chapters, marks them verified: true
5. git commit + push + open PR
6. CI checks: ≤100 new entries, ≥10 verified  →  merge
```

---

## ADR Index

| # | Decision |
|---|---|
| [ADR-0001](docs/adr/0001-single-json-file.md) | Single flat JSON file; consumers self-host |
