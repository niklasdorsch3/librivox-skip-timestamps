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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full setup guide, contribution loop, and tuning options.

The short version: add LibriVox book IDs to `data/books.txt`, run `make run`, verify 10 chapters with `make verify`, open a PR.


## Requirements

- Python 3.10+
- A free [Groq API key](https://console.groq.com) *(recommended — no local GPU needed)*
- `ffmpeg` — `brew install ffmpeg` / `sudo apt install ffmpeg` / [ffmpeg.org](https://ffmpeg.org/download.html)

**Alternative (local, no API key):** Install [Ollama](https://ollama.com/download) and run `ollama pull llama3.2:3b`.

## Setup

```bash
git clone https://github.com/niklasdorsch3/librivox-skip-timestamps.git
cd librivox-skip-timestamps
python3.10 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your OPENAI_API_KEY (Groq key)
```

Verify everything works:

```bash
make demo
```

## Running the pipeline on a single chapter

The fastest way to try the pipeline is to point it at any LibriVox chapter URL:

```bash
make run-chapter URL=https://www.archive.org/download/pride_and_prejudice_librivox/prideandprejudice_01-03_austen_64kb.mp3
```

Or use the included sample to run without a network download:

```bash
make demo
```

Both commands write the result to `data/repository.json` and `data/chapters_to_verify.json` so you can immediately open the verification UI:

```bash
make verify
```

## Development

See [docs/.scratch/](./docs/.scratch/) for user stories and acceptance criteria.

Run the test suite:

```bash
make test
```
