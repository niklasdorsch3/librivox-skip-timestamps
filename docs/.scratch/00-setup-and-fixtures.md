Status: ready-for-agent

## What to build

Project setup: `requirements.txt`, `setup.py`, and the audio test fixture. This slice makes the repo runnable from scratch and provides the audio file the Pipeline integration test depends on.

`requirements.txt` must include: `faster-whisper`, `pydub`, `requests`, `pydantic`.

`setup.py` is a cross-platform Python script that:
- Verifies `ffmpeg` is installed (print actionable instructions if not)
- Verifies `ollama` is installed and running (print instructions if not)
- Pulls the default Ollama model (`llama3.2:3b`) via `ollama pull` if not already present
- Prints a summary of what was checked/installed

The audio fixture is a real LibriVox chapter trimmed to ~20 seconds that contains a real Disclaimer. This has already been selected and added. Commit it to `tests/fixtures/sample_chapter.mp3`. A `tests/fixtures/README.md` documents the source and selection rationale.

## Acceptance criteria

- [ ] `pip install -r requirements.txt` installs all dependencies without error
- [ ] `python setup.py` runs without errors (or prints clear setup instructions if something is missing)
- [ ] Script checks for `ffmpeg` on PATH and prints instructions to install if missing
- [ ] Script checks for `ollama` running (e.g., via HTTP health check to `http://localhost:11434`) and prints instructions if not
- [ ] Script runs `ollama pull llama3.2:3b` if the model is not already present
- [ ] Script prints a clear summary: "✓ ffmpeg installed" / "✓ ollama running" / "✓ model ready"
- [ ] A real LibriVox audio fixture (~20s, contains a Disclaimer) exists in `tests/fixtures/sample_chapter.mp3`
- [ ] `tests/fixtures/README.md` documents the source, selection rationale, and how to replace the fixture
- [ ] The fixture file is committed to the repo

## Blocked by

None — start here. This is the foundation for all other stories.
