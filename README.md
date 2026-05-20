# librivox-skip-timestamps

Community-maintained dataset of LibriVox disclaimer skip timestamps.

LibriVox audiobooks begin each chapter with a spoken disclaimer. This repository contains a public dataset of per-chapter skip timestamps so audiobook apps can jump straight to the content.

## Using the data

Download `repository.json` and serve it from your own app. Each entry maps a LibriVox project ID to its chapters:

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
        "verified": true
      }
    ]
  }
}
```

`exact_audio_skip_seconds` is the point at which the disclaimer ends and the literary content begins. `verified: true` means a human has listened and confirmed the timestamp.

## Contributing

### Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/)
- [Ollama](https://ollama.com/) running locally with `llama3.2:3b` or `gemma2:2b`

### Setup

```bash
pip install -r requirements.txt
ollama pull llama3.2:3b
```

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

PRs that don't meet both requirements will be blocked by CI.

## Tuning

All parameters can be overridden via environment variables:

| Variable | Default | Description |
|---|---|---|
| `WHISPER_MODEL` | `base` | faster-whisper model size (`tiny`, `base`) |
| `OLLAMA_MODEL` | `llama3.2:3b` | Local LLM model |
| `SILENCE_THRESHOLD_DBFS` | `-45` | dBFS level considered silence |
