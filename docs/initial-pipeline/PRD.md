# PRD: Initial Pipeline

Status: ready-for-agent

## Problem Statement

LibriVox audiobooks begin each chapter with a spoken Disclaimer that listeners must manually skip every time. There is no public dataset of skip timestamps. Contributors need a local, fully offline tool to generate these timestamps at scale and publish them as a shared JSON dataset that any audiobook app can consume.

## Solution

A Python pipeline that downloads LibriVox chapters temporarily, transcribes the first 45 seconds locally, uses a local LLM to identify where the Disclaimer ends, refines the boundary with silence detection, and writes the result to a shared `repository.json`. A Verification Script lets contributors confirm 10 entries before submitting a pull request. CI enforces contribution rules automatically.

## User Stories

1. As a contributor, I want to add a list of LibriVox book IDs to `books.txt` and run `main.py`, so that all chapters for those books are processed automatically without me managing audio files locally.
2. As a contributor, I want chapters already present in `repository.json` to be skipped automatically, so that I can resume an interrupted run without re-processing completed work.
3. As a contributor, I want failed chapters to be logged clearly with a reason, so that I can investigate and retry them on the next run.
4. As a contributor, I want audio files to be downloaded temporarily and deleted after processing, so that I don't accumulate gigabytes of audio on my machine.
5. As a contributor, I want the Pipeline to detect when a chapter has no Disclaimer, so that it records `exact_audio_skip_seconds: 0` as a clean result rather than failing.
6. As a contributor, I want the Pipeline to retry a malformed LLM response once before failing, so that transient Ollama errors don't unnecessarily discard a chapter.
7. As a contributor, I want to run `verify.py` after a batch, so that I can interactively confirm randomly selected chapters and mark them as verified before submitting.
8. As a contributor, I want `verify.py` to show me the chapter URL and Pipeline-generated timestamp, so that I can listen and judge accuracy without any extra tooling.
9. As a contributor, I want confirmed entries written to `repository.json` with `"verified": true` automatically, so that I don't have to edit JSON by hand.
10. As a contributor, I want CI to reject my pull request if it contains more than 100 new entries or fewer than 10 verified entries, so that contribution rules are enforced without manual review.
11. As a consumer, I want a single `repository.json` file I can download and self-host, so that I can integrate skip timestamps into my own app without depending on this repo at runtime.
12. As a consumer, I want each chapter entry to include `exact_audio_skip_seconds`, `detected_disclaimer_anchor_word`, and `verified`, so that I have enough context to trust a timestamp.
13. As a contributor, I want `gutenberg_text_id` to be optional in book metadata, so that books without a Project Gutenberg text can still be processed.
14. As a maintainer, I want `repository.json` written atomically, so that an interrupted run never produces a corrupted file.
15. As a contributor, I want all tunable parameters (Whisper model, Ollama model, silence threshold) to be configurable via environment variables, so that I can experiment without changing code.
16. As a contributor, I want the Pipeline to log T_approx, T_exact, and their delta per chapter, so that I can spot poor LLM or silence detection results without re-running the file.

## Implementation Decisions

### Pipeline module (`analyzer.py`)
Exposes a single `run_pipeline(chapter) -> PipelineResult` function. Internally runs three private Stage functions in sequence — Transcription, Boundary Analysis, Silence Detection — each returning a typed result consumed by the next. All Stage coordination and error handling is contained here. `main.py` only sees success or failure with a reason, never partial Stage state. `main.py` is responsible for calling `repository.upsert(result)` after a successful run — the Pipeline has no dependency on the Repository module.

### BoundaryDetector seam
A `BoundaryDetector` module owns the full contract of "given a transcript, return an anchor word or signal no disclaimer." Encapsulates the Ollama HTTP call, retry-once logic, JSON parsing, and `null` vs string branching. Exposes a single function: `detect_boundary(transcript: str) -> BoundaryResult`. Replaceable with an in-memory fake for tests — Stage 2 mapping logic can be tested without a running Ollama instance.

`BoundaryResult` has two states:
- `NoDisclaimer` — LLM returned `null`; chapter records `exact_audio_skip_seconds: 0`
- `AnchorWord(word: str, confidence: float)` — LLM identified the last Disclaimer word

### Repository module
A single `Repository` module owns all reads and writes to `repository.json`. Exposes `load() -> dict`, `upsert(entry)`, `mark_verified(listen_url)`, and `contains(listen_url) -> bool`. All scripts (`main.py`, `verify.py`, `validate_contribution.py`) go through this module. Atomic write, pydantic validation, and skip-check logic live here once. Tests inject an in-memory fake.

### AudioFetcher module
A context-manager module: `with AudioFetcher.fetch(listen_url) as path`. Downloads the chapter to a temp file, yields the path, and deletes on exit regardless of success or failure. Used identically by `main.py` and `verify.py`. Retry and timeout logic live here.

### Contribution validation (`validate_contribution.py`)
Called by CI on every PR. Fetches the base branch version of `repository.json` via `git show origin/main:repository.json`, diffs it against the PR version, and counts new entries. Fails with a clear message if: more than 100 new entries, or fewer than 10 new entries with `"verified": true`.

### Repository schema
```json
{
  "12345": {
    "book_metadata": {
      "librivox_project_id": 12345,
      "gutenberg_text_id": "pg6789",
      "title": "The Art of War"
    },
    "chapters": [
      {
        "file_name": "art_of_war_01_sun_tzu.mp3",
        "listen_url": "https://librivox.org/...",
        "chapter_index": 1,
        "exact_audio_skip_seconds": 15.15,
        "detected_disclaimer_anchor_word": "domain",
        "verified": false
      }
    ]
  }
}
```
`gutenberg_text_id` is nullable. `detected_disclaimer_anchor_word` is `null` when no Disclaimer was detected. `approximate_text_end` (T_approx) is computed internally by the Pipeline, logged per chapter (e.g. `t_approx: 14.21s  t_exact: 15.15s  delta: +0.94s`), and used for the Outlier check — but not written to `repository.json`.

## Testing Decisions

Good tests exercise the external interface of a module without knowledge of its internals. Tests should not mock internal Stage functions — only cross-seam dependencies (Ollama, LibriVox API, filesystem).

**BoundaryDetector** — highest priority. Test all outcomes (clean anchor word, no disclaimer, malformed JSON triggers retry, two malformed responses fails) using a fake HTTP adapter. No Ollama instance required.

**Repository module** — test `upsert`, `mark_verified`, `contains`, and atomic write behaviour using a temp file. Test that a corrupt mid-write does not leave the file in a bad state.

**Pipeline (`run_pipeline`)** — integration test with a real audio fixture and a fake `BoundaryDetector`. Verifies the full Stage sequence produces the correct `PipelineResult` shape. The fixture is a real LibriVox chapter trimmed to ~20 seconds (contains a real Disclaimer) stored in `tests/fixtures/`.

**`validate_contribution.py`** — unit test with synthetic before/after `repository.json` dicts. Cover: exactly 100 new entries passes, 101 fails; exactly 10 verified passes, 9 fails.

**`main.py` / `verify.py`** — not unit tested. Covered by the module tests above; end-to-end behaviour verified manually during a real batch run.

## Out of Scope

- Streaming audio (chapters are downloaded to temp files)
- A web UI or hosted API for consuming timestamps
- Automatic scraping of the full LibriVox catalog
- Per-book JSON files (deferred per ADR-0001)
- Multi-language support

## Further Notes

- The easy-audiobook player is the primary consumer of `repository.json`. Contributors should seed `books.txt` with the easy-audiobook Curated Shelf book IDs first.
- `verify.py` picks chapters at random from new entries — contributors cannot pre-select easy ones. If fewer than 10 new entries exist, all of them are presented for verification. CI still requires at least 10 verified entries before a PR can merge, so contributors with small batches must run more books before submitting.
- The Silence Threshold (−45 dBFS), scan window (3 s), scan step (50 ms), and Processing Threshold (45 s) are constants that can be overridden via environment variables for tuning purposes.
