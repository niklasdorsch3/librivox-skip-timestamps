# Contributing to librivox-skip-timestamps

Thank you for helping grow the dataset. Each contribution adds verified skip
timestamps that LibriVox listeners can use to jump straight to the content,
forever.

---

## What a contribution looks like

A pull request that adds up to **100 new chapter entries** to `data/repository.json`,
of which at least **10 are verified** — meaning you personally listened and
confirmed the skip time is correct.

CI will check both requirements and post a summary comment on every PR.
Violations are warnings, not blockers, but reviewers will ask you to fix them.

---

## Requirements

- Python 3.10+
- A free [Groq API key](https://console.groq.com) *(recommended — no local GPU needed)*
- `ffmpeg` installed on your system
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: [ffmpeg.org/download](https://ffmpeg.org/download.html)

**Alternative (local, no API key):** Install [Ollama](https://ollama.com/download),
then run `ollama pull llama3.2:3b`. Set `OLLAMA_MODEL=llama3.2:3b` in your `.env`.

---

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

Verify your setup works end-to-end in one command:

```bash
make demo
```

This downloads a sample LibriVox chapter, runs the full pipeline, and prints the
detected skip timestamp. If it completes without error, you're ready.

---

## Contribution loop

### 1. Pick books

Add LibriVox book IDs to `books.txt`, one per line. Find IDs on
[librivox.org](https://librivox.org) — the ID is the number in the URL, e.g.
`https://librivox.org/the-art-of-war-by-sun-tzu/` → `1234`.

```
1234
5678
```

### 2. Run the pipeline

```bash
make run
```

This fetches all chapters for each book, runs the timestamp pipeline, and writes
results to `data/repository.json`. Already-processed chapters are skipped
automatically. Progress is logged to stdout.

### 3. Verify 10 chapters

```bash
make verify
```

A browser UI opens. For each of the 10 sampled chapters (outliers first), an
audio player starts at the detected skip time. Listen and confirm:

- **Approve ✓** — the skip lands correctly at the start of the literary content
- **Deny ✗** — the skip is wrong; stops verification and prints instructions for
  filing a bug

After 10 approvals the server shuts down and prompts you to open a PR.

### 4. Open a pull request

The `verify` script offers to commit and run `gh pr create` automatically.
Or manually:

```bash
git add data/repository.json
git commit -m "feat: add timestamps for <book title(s)>"
git push origin main
gh pr create --fill
```

---

## Rules

| Rule | Limit | Effect |
|---|---|---|
| New entries per PR | ≤ 100 | Warning comment from CI if exceeded |
| Verified entries per PR | ≥ 10 | Warning comment from CI if under |

Both are soft limits — they flag the contribution for reviewer attention but do
not block merge.

---

## Tuning the pipeline

All parameters are controlled via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | _(unset)_ | Groq (or any OpenAI-compatible) API key |
| `OPENAI_API_BASE` | `https://api.groq.com/openai/v1` | API base URL |
| `OPENAI_MODEL` | `llama-3.1-8b-instant` | Model for boundary detection |
| `OLLAMA_MODEL` | `llama3.2:3b` | Local model (used when no API key is set) |
| `WHISPER_MODEL` | `base` | faster-whisper model size (`tiny` or `base`) |
| `SILENCE_THRESHOLD_DBFS` | `-45` | dBFS level considered silence |
| `CONFIDENCE_THRESHOLD` | `0.5` | Minimum LLM confidence to accept an anchor |

---

## Code contributions

Bug reports, pipeline improvements, and tooling fixes are welcome. Please open
an issue before starting large changes so we can discuss the approach.

Run the test suite before submitting:

```bash
make test
```

All logic changes (pipeline stages, timestamp detection, batch processing,
output formatting) require tests. See `AGENTS.md` for the full testing policy.
