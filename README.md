# librivox-skip-timestamps

Community-maintained dataset of LibriVox disclaimer skip timestamps.

LibriVox audiobooks begin each chapter with a spoken disclaimer. This repository contains a public dataset of per-chapter skip timestamps so audiobook apps can jump straight to the content.

## Using the data

Download `data/repository.json` and serve it from your own app. Each entry maps a LibriVox project ID to its chapters:

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
        "chapter_index": 1,
        "chapter_title": "Chapter 1: The Laying of Plans",
        "listen_url": "https://librivox.org/...",
        "exact_audio_skip_seconds": 15.15,
        "detected_disclaimer_anchor_word": "domain",
        "is_outlier": false,
        "verified": true
      }
    ]
  }
}
```

`exact_audio_skip_seconds` is the point at which the disclaimer ends and the literary content begins. `verified: true` means a human has listened and confirmed the timestamp. `is_outlier: true` means the pipeline's LLM and silence-detection results diverged significantly — treat these entries with extra care.

## Development

See [docs/.scratch/](./docs/.scratch/) for user stories and acceptance criteria. Stories are ordered for TDD:

**00 — Setup & Fixtures** (foundation)
**01-07 — Implementation** (unit tests with mocks in Codespace; integration tests deferred)

To develop in a Codespace without ffmpeg/ollama:
- Use dependency injection and mocks for HTTP calls (Ollama, LibriVox API)
- Mock file I/O and audio processing
- Unit tests pass; integration tests skipped until proper environment

## Contributing

### Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/)
- [Ollama](https://ollama.com/) running locally with `llama3.2:3b` or `gemma2:2b`

### Setup

**1. Install Ollama**

Ollama runs LLMs locally. Download it from [ollama.com](https://ollama.com/download) and install it like a normal app. Once installed, it runs as a background service.

**2. Pull a model**

```bash
ollama pull llama3.2:3b
```

This downloads the model (~2GB) once. You can verify it's working:

```bash
ollama run llama3.2:3b "hello"
```

**3. Install Python dependencies**

```bash
pip install -r requirements.txt
```

`faster-whisper` (used for transcription) will download the Whisper model automatically on first run (~150MB for `base`).

### Running a batch

1. Add LibriVox book IDs to `books.txt` (one per line)
2. Run the pipeline:
   ```bash
   python main.py
   ```
3. Verify 10 entries manually:
   ```bash
   python verify.py
   ```
4. Open a pull request

### Contribution rules

Pull requests are automatically checked for:

- **≤ 100** new chapter entries
- **≥ 10** entries with `"verified": true`

PRs that don't meet both requirements will receive a warning comment from CI. Violations do not block merge — they flag the contribution for reviewer attention.

## Tuning

All parameters can be overridden via environment variables:

| Variable | Default | Description |
|---|---|---|
| `WHISPER_MODEL` | `base` | faster-whisper model size (`tiny`, `base`) |
| `OLLAMA_MODEL` | `llama3.2:3b` | Local LLM model (used when `OPENAI_API_KEY` is not set) |
| `SILENCE_THRESHOLD_DBFS` | `-45` | dBFS level considered silence |
| `CONFIDENCE_THRESHOLD` | `0.5` | Minimum LLM confidence to accept an anchor word |
| `OPENAI_API_KEY` | _(unset)_ | When set, uses an OpenAI-compatible API instead of local Ollama |
| `OPENAI_API_BASE` | `https://api.groq.com/openai/v1` | API base URL for the OpenAI-compatible endpoint |
| `OPENAI_MODEL` | `llama-3.1-8b-instant` | Model name for the OpenAI-compatible endpoint |
