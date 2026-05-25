Status: ready-for-agent

# Make Groq the default, zero-ffmpeg setup path

## Problem

The current setup requires contributors to install ffmpeg (a system dependency)
and either Ollama (a local LLM runtime + ~2GB model download) or configure a
Groq API key. On a cold machine this takes 20+ minutes and is the single biggest
source of contributor drop-off. The Groq path (free API key, no local GPU) is
already fully implemented but buried as an advanced option.

Additionally, `faster-whisper` requires ffmpeg as a system dependency. This is
the hardest part of the setup on Windows and CI environments.

## Goal

A contributor with a free Groq API key and Python 3.10+ should be able to run
`make demo` and see a correct skip timestamp within **3 minutes** of cloning the
repo, with no system-level installs beyond Python.

## Proposed approach

### 1. Groq as the hero path in docs

- Rewrite the "Requirements" section in `CONTRIBUTING.md` and `README.md` so
  Groq + API key is the first and most prominent setup option.
- Ollama becomes the "local/offline alternative" in a collapsed section or
  footnote.

### 2. Replace ffmpeg system dependency with `static-ffmpeg`

`static-ffmpeg` (already used in `run_pipeline.py`) downloads a static ffmpeg
binary on first use — no system install required. Extend this to all pipeline
entry points:
- `main.py` should call `static_ffmpeg.add_paths()` at startup (same as
  `run_pipeline.py` already does).
- Add `static-ffmpeg` to `requirements.txt`.
- Update `setup.py` to skip the ffmpeg system check when `static-ffmpeg` can
  provide it, or remove the check entirely.

### 3. Investigate replacing local Whisper with Groq Whisper API

Groq exposes a Whisper transcription endpoint. If the boundary detector already
routes through Groq when `OPENAI_API_KEY` is set, consider doing the same for
transcription — eliminating `faster-whisper` and the Whisper model download
(~150 MB) from the default path entirely.

This is a pipeline architecture change and needs a separate ADR if adopted.

## Acceptance criteria

- [ ] `make demo` completes successfully on a machine with only Python 3.10+
      and a Groq API key — no ffmpeg system install, no Ollama
- [ ] `README.md` and `CONTRIBUTING.md` lead with the Groq path
- [ ] `static-ffmpeg` is in `requirements.txt` and called at all entry points
- [ ] Existing tests continue to pass
- [ ] If Groq Whisper is adopted: new ADR documents the decision

## Out of scope

- Removing Ollama/local support — it stays as an option
- Changing the pipeline logic or timestamp accuracy
