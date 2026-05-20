# Design Philosophy

- **Local and free, unconditionally.** No external APIs at runtime. No token costs, no rate limits, no API keys. If a solution requires a paid service, the solution is wrong.

- **Resumable by default.** Processing hundreds of audio files takes hours. The system must survive interruption — power loss, crashes, network drops — and pick up exactly where it left off. Checkpoint before you proceed, not after.

- **Never corrupt the output.** `repository.json` is the public artefact. A partial write is worse than no write. Write atomically. Validate with pydantic before touching the file.

- **Fail loudly, fall back gracefully.** When the LLM returns garbage, don't crash the Batch Runner — activate the Fallback, flag the entry, and move on. But log the failure clearly so it can be fixed later.

- **Flag rather than discard.** Outliers and low-confidence results are not errors to be hidden — they are signals to be surfaced in the Repository. A flagged entry is more useful than a silently skipped one.

- **One pipeline, no magic.** Each Stage has one job and one output. Data flows forward; no Stage reads back from a later Stage. The Pipeline is a function: audio file in, timestamp out.
