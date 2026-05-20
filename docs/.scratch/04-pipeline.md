Status: ready-for-agent

## What to build

A Pipeline module exposing a single `run_pipeline(chapter) -> PipelineResult` function. Runs three Stages in sequence — Transcription, Boundary Analysis, Silence Detection — each producing a typed result consumed by the next. All Stage coordination and error handling lives here. The caller only sees success or a typed failure with a reason.

**Stage 1 — Transcription:** load only the first 45 seconds of the audio file, run faster-whisper locally, return a Token Map (`list[tuple[str, float]]` — word + end time in seconds). Whisper model is configurable via `WHISPER_MODEL` env var (default: `base`).

**Stage 2 — Boundary Analysis:** pass the transcript to `BoundaryDetector`. If `NoDisclaimer`, return a `PipelineResult` with `exact_audio_skip_seconds: 0` immediately — skip Stage 3. If `AnchorWord`, look up the word in the Token Map to get T_approx. If the word is not found, raise a typed failure.

**Stage 3 — Silence Detection:** extract a 3-second audio window from T_approx using pydub, scan in 50ms steps measuring dBFS, find the first point below the Silence Threshold (−45 dBFS) to produce T_exact. If no silence is found, T_exact = T_approx.

Log per chapter: `t_approx: 14.21s  t_exact: 15.15s  delta: +0.94s`. Flag as Outlier if delta > 4s.

`PipelineResult` includes: `exact_audio_skip_seconds`, `detected_disclaimer_anchor_word` (null if no Disclaimer), `verified: false`. T_approx is not included in the result — it is logged only.

All tunable constants (`SILENCE_THRESHOLD_DBFS`, `WHISPER_MODEL`) are configurable via environment variables.

A real LibriVox chapter trimmed to ~20 seconds lives in `tests/fixtures/` for use in integration tests.

## Acceptance criteria

- [ ] `run_pipeline` returns a `PipelineResult` with `exact_audio_skip_seconds: 0` when no Disclaimer is detected
- [ ] `run_pipeline` returns a `PipelineResult` with the correct `exact_audio_skip_seconds` for a chapter with a Disclaimer
- [ ] T_approx and T_exact are logged per chapter with their delta
- [ ] Entries where delta > 4s are flagged as Outliers in the log
- [ ] Anchor Word not found in Token Map raises a typed failure
- [ ] `SILENCE_THRESHOLD_DBFS` and `WHISPER_MODEL` env vars are respected
- [ ] Integration test uses a real audio fixture and a fake `BoundaryDetector`
- [ ] Audio fixture committed to `tests/fixtures/`

## Blocked by

- 02-boundary-detector.md
- 03-audio-fetcher.md
