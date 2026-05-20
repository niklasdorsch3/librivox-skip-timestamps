# librevox-timestamps — Domain Glossary

Data pipeline that produces skip timestamps for LibriVox audiobooks. Output is consumed by the easy-audiobook player to automatically skip the spoken Disclaimer at the start of each chapter.

## Pipeline

The full automated process that takes a LibriVox audio file as input and produces a verified skip timestamp as output. Consists of four sequential Stages: Transcription, Boundary Analysis, Silence Detection, and Repository Update. Each Stage hands off a typed result to the next.

---

## Stage

One discrete step in the Pipeline. There are four Stages:

1. **Transcription** — converts the first 45 seconds of audio to word tokens with timestamps
2. **Boundary Analysis** — identifies the last word of the Disclaimer using a local LLM
3. **Silence Detection** — finds the exact silence onset after the Disclaimer ends

Stages are run sequentially per chapter. The Pipeline returns a typed result — it has no dependency on the Repository. The caller (`main.py`) is responsible for writing the result to the Repository.

---

## Disclaimer

The standard LibriVox spoken introduction at the start of each audio chapter, read by a volunteer. Ends just before the literary text begins. The Pipeline's goal is to find the precise moment the Disclaimer ends so listeners can skip directly to the content. The Disclaimer is the unit of work the LLM reasons about.

Expected on every chapter, but not guaranteed — some chapters have no Disclaimer (e.g. silent intros, non-standard recordings). When Stage 2 detects no Disclaimer is present, the chapter is recorded in the Repository with `exact_audio_skip_seconds: 0` and flagged as `no_disclaimer`.

---

## Anchor Word

The last word belonging to the Disclaimer, as identified by the LLM in Stage 2. Used to locate an approximate timestamp (T_approx) by looking up the word in the Token Map produced in Stage 1.

---

## Token Map

The data structure produced by Stage 1: an ordered list of `(word, end_time_seconds)` pairs covering the first 45 seconds of the audio file. Used in Stage 2 to map the Anchor Word back to a time position.

---

## T_approx

The approximate timestamp (in seconds) of the end of the Disclaimer, derived by looking up the Anchor Word in the Token Map. Carries LLM uncertainty; refined by Stage 3. Only exists when the Disclaimer is present — chapters with no Disclaimer go directly to a result of 0 without producing a T_approx.

---

## T_exact

The precise timestamp (in seconds) at which silence begins after the Disclaimer ends, measured by Stage 3. Computed by scanning a 3-second window forward from T_approx in 50 ms steps and finding the first point that drops below the Silence Threshold (−45 dBFS). This is the value written to the Repository as `exact_audio_skip_seconds`.

---

## Silence Threshold

The audio level below which a segment is classified as silence: −45 dBFS. Used exclusively in Stage 3. A drop below this threshold within the 3-second scan window defines the boundary between the Disclaimer and the literary content.

---

## Confidence Score

A 0.0–1.0 float returned by the LLM in Stage 2 alongside the Anchor Word. Indicates how certain the model is that it found the correct Disclaimer boundary. Low-confidence results are flagged in the Repository for manual review.

---

## Batch Runner

The entry-point script (`main.py`) that reads a flat list of LibriVox book IDs from `books.txt`, fetches all chapters for each book from the LibriVox API, skips chapters already present in `repository.json`, and invokes the Pipeline per chapter. Audio is never stored permanently — each chapter is downloaded to a temporary file, processed, then deleted. Failed chapters are logged to stdout and retried on the next run.

---

## Repository

The output JSON file (`repository.json`) that maps LibriVox project IDs to per-chapter timestamp data. The canonical public artefact of this project. Schema:

```json
{
  "book_metadata": {
    "librivox_project_id": 12345,
    "gutenberg_text_id": "pg6789",
    "title": "The Art of War"
  },
  "chapters": [
    {
      "file_name": "art_of_war_01_sun_tzu.mp3",
      "chapter_index": 1,
      "approximate_text_end": 14.21,
      "exact_audio_skip_seconds": 15.15,
      "detected_disclaimer_anchor_word": "domain",
      "verified": false
    }
  ]
}
```

---

## Outlier

A chapter entry where the difference between `approximate_text_end` (T_approx) and `exact_audio_skip_seconds` (T_exact) exceeds 4 seconds. Flagged in the Repository for manual review. A high outlier count signals that either the LLM or the Silence Detection Stage needs tuning. Chapters with no Disclaimer (`exact_audio_skip_seconds: 0`) are never Outliers.

---

## Contribution

A batch of up to 100 timestamps submitted to the Repository by a contributor, via pull request. Each Contribution must include exactly 10 Verified Entries. The remaining entries are pipeline-generated and unverified.

---

## Verified Entry

A chapter entry in the Repository that a human has listened to and confirmed the `exact_audio_skip_seconds` is correct. Marked with `"verified": true` in the Repository. Every Contribution must contain at least 10 Verified Entries.

---

## Golden Set

The 10 Verified Entries within a Contribution — the chapters the contributor personally listened to and confirmed via the Verification Script. Not a fixed global file; each Contribution brings its own Golden Set.

---

## Verification Script

A standalone script (`verify.py`) run after the Batch Runner completes. Picks 10 chapters at random from the new batch output, presents each one to the contributor (chapter URL + Pipeline-generated timestamp), and prompts them to confirm or reject. Confirmed entries are written back to the output with `"verified": true`. Once 10 entries are verified, the output is ready to submit as a Contribution.

---

## Processing Threshold

The maximum amount of audio analysed per file: 45 seconds from the start. No Disclaimer is expected to exceed this window. A safety check ensures `exact_audio_skip_seconds` never exceeds this value.
