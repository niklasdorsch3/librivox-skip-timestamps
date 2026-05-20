Status: ready-for-agent

## What to build

A `Repository` module that owns all reads and writes to `repository.json`. Every other script in the codebase goes through this module — none of them touch the file directly.

The module exposes four operations: load the full repository, upsert a chapter entry, mark an entry as verified by its `listen_url`, and check whether a `listen_url` already exists. All writes are atomic — write to a temp file then rename — so an interrupted run never corrupts the file. All entries are validated against a pydantic schema before writing. The schema matches the structure defined in the PRD: one top-level key per LibriVox project ID, each with `book_metadata` and a `chapters` array. `gutenberg_text_id` is nullable.

## Acceptance criteria

- [ ] `load()` returns the full repository dict (empty dict if file doesn't exist)
- [ ] `upsert(entry)` adds a new chapter entry or updates an existing one matched by `listen_url`
- [ ] `mark_verified(listen_url)` sets `verified: true` on the matching entry
- [ ] `contains(listen_url)` returns `True` if the chapter already exists
- [ ] All writes are atomic — temp file + rename
- [ ] Pydantic validation rejects entries with missing required fields
- [ ] `gutenberg_text_id` is accepted as `null`
- [ ] Tests cover `upsert`, `mark_verified`, `contains`, and atomic write behaviour using a temp file
- [ ] Test confirms a simulated mid-write crash does not corrupt the existing file

## Blocked by

None — can start immediately.
