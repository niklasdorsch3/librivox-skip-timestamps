Status: ready-for-agent

## What to build

The `main.py` Batch Runner — the entry point contributors run to process a batch of books. Reads LibriVox book IDs from `books.txt` (one per line), fetches all chapters for each book from the LibriVox API, skips chapters already in `repository.json`, downloads each chapter via `AudioFetcher`, runs `run_pipeline`, and writes the result via `repository.upsert()`.

Logs per chapter:
- `✓ <title> — <chapter>` — success
- `~ <title> — <chapter> (no disclaimer)` — clean result, no Disclaimer
- `✗ <title> — <chapter> — <reason>` — failed

Prints a summary at the end of the run: total processed, succeeded, no-disclaimer, failed. Failed chapters are listed with their error reason.

Writes a manifest of all new chapters generated in this run to `chapters_to_verify.json` (a simple list of `listen_url` values). The Verification Script reads this to scope verification to only this run's work.

## Acceptance criteria

- [ ] Reads book IDs from `books.txt`, one per line
- [ ] Fetches chapter list from the LibriVox API for each book
- [ ] Skips chapters whose `listen_url` already exists in `repository.json`
- [ ] Downloads each chapter temporarily via `AudioFetcher`, deletes after processing
- [ ] Calls `run_pipeline` and writes result to `repository.json` via `repository.upsert()`
- [ ] Logs `✓ / ~ / ✗` per chapter with reason on failure
- [ ] Prints end-of-run summary with counts and list of failed chapters
- [ ] A single chapter failure does not stop the rest of the batch
- [ ] Failed chapters are NOT written to `repository.json`; they will be retried on the next run

## Blocked by

- 01-repository-module.md
- 03-audio-fetcher.md
- 04-pipeline.md
