# librevox-timestamps — Architecture

> For domain terminology (Pipeline, Stage, Disclaimer, Repository, etc.) see [`CONTEXT.md`](CONTEXT.md).
> For individual architectural decisions and their rationale see [`adr/`](adr/).

---

## System Overview

A local Python pipeline that processes LibriVox audio files and produces a public JSON Repository of per-chapter skip timestamps. By default all inference runs locally via faster-whisper and Ollama. An optional OpenAI-compatible API path (e.g. Groq) is available when `OPENAI_API_KEY` is set — see the environment table below.

This repository is a data companion to the **easy-audiobook** player. `repository.json` is a public dataset — consumers download it and serve it themselves from within their own app. It is not fetched at runtime from this repo.

```
┌─────────────────────────────────────────────────────┐
│                   Batch Runner (main.py)             │
│  reads data/books.txt · fetches chapters · skips known   │
│                                                      │
│  ┌───────────────────────────────────────────────┐  │
│  │              Pipeline (analyzer.py)           │  │
│  │                                               │  │
│  │  Stage 1: Transcription (faster-whisper)      │  │
│  │     └─▶ Token Map [(word, end_time_s), ...]   │  │
│  │                                               │  │
│  │  Stage 2: Boundary Analysis (Ollama / LLM)    │  │
│  │     └─▶ Anchor Word + Confidence → T_approx  │  │
│  │                                               │  │
│  │  Stage 2b: Chapter Heading Detection          │  │
│  │     └─▶ (optional) T_chapter_end → T_ref     │  │
│  │                                               │  │
│  │  Stage 3: Silence Detection (pydub / ffmpeg)  │  │
│  │     └─▶ T_exact · outlier flag · safety check│  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  repository.upsert(PipelineResult)                   │
└────────────────────────┬────────────────────────────┘
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

Entry point. Reads a flat list of LibriVox book IDs from `data/books.txt` (one ID per line), fetches all chapters for each book from the LibriVox API, and skips any chapter whose `listen_url` already exists in `repository.json`. Failed chapters are logged to stdout with their error reason and retried on the next run. Downloads the chapter audio to a temporary file, invokes the Pipeline, then deletes the temporary file regardless of success or failure. Audio never persists to disk beyond the duration of a single chapter's processing.

Logs to stdout per chapter:
- `✓ <title> — <chapter>` — completed successfully
- `~ <title> — <chapter> (no disclaimer)` — completed, no Disclaimer detected
- `✗ <title> — <chapter> — <reason>` — failed (e.g. "LLM returned malformed JSON after retry", "Anchor Word not found in Token Map")

At the end of each run, prints a summary: total processed, succeeded, no-disclaimer, failed. Failed chapters are listed with their error reason so they can be investigated or re-run.

Writes a manifest of all new chapters generated in the run to `chapters_to_verify.json` (a JSON array of `listen_url` strings). The Verification Script uses this to scope its random sample to only this run's output.

### `analyzer.py` — Pipeline

Implements three Stages sequentially — Transcription, Boundary Analysis, Silence Detection. Returns a typed `PipelineResult` or raises a typed exception. Has no global state — all data flows through function arguments and return values. Has no dependency on the Repository module — `main.py` calls `repository.upsert(result)` after a successful run.

#### Stage 1 — Transcription

- Receives a path to a temporary local audio file (downloaded by the Batch Runner).
- Loads only the first 45 seconds.
- Runs `faster-whisper` locally (model: `tiny` or `base`, CPU or GPU).
- Returns a **Token Map**: `list[tuple[str, float]]` — `(word, end_time_seconds)`.

#### Stage 2 — Boundary Analysis

- Sends the full transcribed text block to the configured LLM (local Ollama by default; OpenAI-compatible API when `OPENAI_API_KEY` is set).
- Default local model: `llama3.2:3b`. Configurable via `OLLAMA_MODEL`.
- Prompt instructs the model to identify the **Anchor Word** — the last word of the Disclaimer.
- Response schema: `{"disclaimer_end_word": str | null, "confidence_score": float}`. `null` means no Disclaimer detected — clean success, recorded as `exact_audio_skip_seconds: 0`.
- If confidence is below `CONFIDENCE_THRESHOLD` (default 0.5), treated as NoDisclaimer.
- If the response is malformed JSON: retry once. If still malformed: raises `BoundaryDetectionError`; `main.py` logs the failure and moves to the next chapter.
- If the Anchor Word cannot be located in the Token Map: raises `AnchorWordNotFoundError`.
- On success, maps the Anchor Word to its position in the Token Map to obtain **T_approx**.

#### Stage 2b — Chapter Heading Detection (optional)

- After T_approx is found, scans the Token Map up to 8 seconds ahead for a chapter heading keyword (`chapter`, `part`, `book`, `prologue`, `epilogue`, `preface`, `introduction`).
- If a heading is found, the scan window for Stage 3 shifts: instead of scanning 3 s forward from T_approx, the pipeline scans the gap between T_approx and the heading word's end time (`T_chapter_end`) to find the last substantial silence→audio transition (i.e. where spoken content resumes after the heading).
- Uses a looser silence threshold (−38 dBFS vs −45 dBFS) for this gap scan.
- The reference point for the outlier check and logging becomes `T_ref = T_chapter_end` when this stage fires; otherwise `T_ref = T_approx`.
- If no qualifying transition is found in the gap, falls back to `T_chapter_end` as T_exact.

#### Stage 3 — Silence Detection

- Standard path (no chapter heading): extracts a 3-second audio window starting at T_approx using `pydub`, scans in 50 ms steps, finds the first step below the Silence Threshold (−45 dBFS) — this is **T_exact**.
- If no silence is found in the window, T_exact = T_approx.
- Safety check: T_exact is clamped to 45 s.
- Outlier flag: set if |T_exact − T_ref| > 4 s. Computed here in `analyzer.py` and included in `PipelineResult`.
- Logs: `t_ref: <s>  t_exact: <s>  delta: <±s>  [OUTLIER]`

The `PipelineResult` returned to `main.py` contains: `exact_audio_skip_seconds`, `detected_disclaimer_anchor_word`, `is_outlier`, `verified`. `main.py` then calls `repository.upsert()` to write it — the Pipeline has no dependency on the Repository module.

### `audio_fetcher.py` — Audio Fetcher

Downloads a LibriVox chapter audio file to a temporary location and cleans up after use. Used as a context manager so the temp file is always deleted — on success or on failure — without callers managing cleanup.

Exposes a single interface:

- `AudioFetcher.fetch(listen_url, session?) -> ContextManager[str]` — downloads the file, yields its local path, then deletes the temp file on exit. Retries once on transient `requests` errors; raises `AudioFetchError` if all attempts fail.

The `session` parameter accepts any `requests.Session`-compatible object for testing without real network access.

### `boundary_detector.py` — Boundary Detector

Owns the full contract of "given a transcript, return where the Disclaimer ends." Encapsulates the Ollama HTTP call, retry-once logic, JSON parsing, and the `NoDisclaimer` vs `AnchorWord` branching.

Exposes a single public function:

- `detect_boundary(transcript, session?) -> BoundaryResult` — calls Ollama, returns `AnchorWord(word, confidence)` or `NoDisclaimer`. Retries once on malformed JSON; raises `BoundaryDetectionError` if both attempts fail.

`BoundaryResult` is `Union[NoDisclaimer, AnchorWord]`. The `session` parameter accepts any `requests.Session`-compatible object, enabling tests to inject a fake HTTP adapter without a running Ollama instance.

The model is controlled by the `OLLAMA_MODEL` environment variable (default: `llama3.2:3b`).

### `repository.py` — Repository Module

Owns all reads and writes to `repository.json`. No other module touches the file directly. Exposes four operations:

- `load(path)` — returns the full repository dict; empty dict if file doesn't exist.
- `upsert(entry, path)` — validates `entry` via pydantic (`UpsertPayload` → `BookMetadata` + `ChapterEntry`), then adds or updates the matching chapter (by `listen_url`) within its project-ID bucket.
- `mark_verified(listen_url, path)` — sets `verified: true` on the matching chapter entry.
- `contains(listen_url, path)` — returns `True` if the chapter already exists.

All writes go through `_atomic_write`: data is serialised to a temp file in the same directory, then `os.replace`d into place. An interrupted run never corrupts the file. The temp file is cleaned up on failure.

---

### `verify.py` — Verification Script

Run after `main.py` completes. Reads `chapters_to_verify.json` (written by `main.py`) to identify the new batch output, selects up to 10 chapters (outliers first, then random), starts a local web server on `localhost:8765`, and opens a browser UI for the contributor to review each chapter.

**Selection strategy:** All chapters where `is_outlier: true` are prioritised (up to 10); remaining slots are filled at random from non-outliers. Contributors cannot pre-select entries.

**Browser UI per chapter:** Book title, chapter number, `listen_url` (clickable), pipeline-generated `exact_audio_skip_seconds`, and an `[OUTLIER: delta Xs]` warning when applicable. An HTML5 audio player starts at the skip timestamp. Buttons: "Play from 5s before", "Seek to skip time", "Approve ✓", "Deny ✗".

- **Approve:** calls `repository.mark_verified(listen_url)` and advances to the next chapter.
- **Deny:** stops immediately; displays "Verification failed: Pipeline produced incorrect result. File a bug and fix the pipeline before rerunning."

After 10 approvals (or all chapters when fewer than 10 are available), the server shuts down and the terminal prompts: "Create PR now? (y/n)". On `y`, the script commits `repository.json` and runs `gh pr create` with an auto-generated description. On `n`, it prints the git/gh commands for the contributor to run manually.

If fewer than 10 chapters are available and `--override` is not set, exits with: "Only N chapters verified (need 10 minimum). Run `python verify.py --override` to proceed."

`--override` flag: allows PR creation with fewer than 10 verified chapters (minimum 1).

Does not re-run the Pipeline — only marks existing output verified.

### `.github/workflows/validate-contribution.yml` — CI check

Runs on every pull request to `main`. Executes `validate_contribution.py` which diffs `repository.json` against the base branch and posts a summary comment on the PR with:

- Total new entries and verified count (always shown)
- ⚠️ warning if more than 100 new entries — suggests splitting the PR
- ⚠️ warning if fewer than 10 verified entries — suggests running more books or using `--override`
- ✓ if both checks pass

Violations are **warnings only** and do not block merge. No other checks — does not validate timestamp values or re-run the Pipeline. On re-push the bot comment is updated in-place rather than duplicated.

### `validate_contribution.py` — Contribution validator

Compares two `repository.json` snapshots (PR vs. base branch) and prints a Markdown summary to stdout. Pure logic module — no GitHub API calls; the workflow handles posting.

Public functions:
- `load_json(path)` — loads a repository JSON file; returns `{}` if missing or empty.
- `find_new_chapters(pr_repo, base_repo)` — returns chapters present in `pr_repo` but absent (by `listen_url`) from `base_repo`.
- `count_verified(chapters)` — counts chapters with `"verified": true`.
- `build_comment(total_new, verified)` — formats the PR comment body.

CLI: `python validate_contribution.py --pr-repo repository.json --base-repo /tmp/base.json`

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

| Variable | Default | Description |
|---|---|---|
| `WHISPER_MODEL` | `base` | faster-whisper model (`tiny`, `base`) |
| `OLLAMA_MODEL` | `llama3.2:3b` | Local LLM model (used when `OPENAI_API_KEY` is not set) |
| `SILENCE_THRESHOLD_DBFS` | `−45.0` | dBFS level considered silence in Stage 3 |
| `CONFIDENCE_THRESHOLD` | `0.5` | Minimum LLM confidence to accept an anchor word |
| `OPENAI_API_KEY` | _(unset)_ | When set, routes LLM calls to an OpenAI-compatible API instead of Ollama |
| `OPENAI_API_BASE` | `https://api.groq.com/openai/v1` | Base URL for the OpenAI-compatible endpoint |
| `OPENAI_MODEL` | `llama-3.1-8b-instant` | Model name for the OpenAI-compatible endpoint |

---

## Contribution workflow

```
1. Fork the repo
2. Add LibriVox book IDs to data/books.txt
3. python main.py              # downloads + processes chapters, writes to repository.json
4. python verify.py            # browser UI — approve 10 chapters, marks them verified: true
5. git commit + push + open PR
6. CI checks: ≤100 new entries, ≥10 verified  →  merge
```

---

## ADR Index

| # | Decision |
|---|---|
| [ADR-0001](docs/adr/0001-single-json-file.md) | Single flat JSON file; consumers self-host |
