Status: ready-for-agent

## What to build

Project setup: `requirements.txt`, `setup.sh`, and the audio test fixture. This slice makes the repo runnable from scratch and provides the audio file the Pipeline integration test depends on.

`requirements.txt` must include: `faster-whisper`, `pydub`, `requests`, `pydantic`.

`setup.sh` must verify that `ffmpeg` and `ollama` are installed (print clear instructions if not), then pull the required Ollama model if not already present.

The audio fixture is a real LibriVox chapter trimmed to ~20 seconds that contains a real Disclaimer. A human must select, download, and trim this file — it cannot be automated. Commit it to `tests/fixtures/`.

## Acceptance criteria

- [ ] `pip install -r requirements.txt` installs all dependencies without error
- [ ] `./setup.sh` checks for `ffmpeg` and prints an actionable message if missing
- [ ] `./setup.sh` checks for `ollama` and prints an actionable message if missing
- [ ] `./setup.sh` pulls the required model if not already present
- [ ] A real LibriVox audio fixture (~20s, contains a Disclaimer) exists in `tests/fixtures/`
- [ ] The fixture file is committed to the repo

## Blocked by

None — can start immediately. Audio fixture requires human selection and trimming.
