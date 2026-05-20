Status: ready-for-agent

## What to build

The `verify.py` Verification Script — run by a contributor after `main.py` to confirm 10 chapters before submitting a PR. Starts a local web server with a browser UI. Reads the manifest `chapters_to_verify.json` (written by `main.py`) to identify which chapters were generated in this run. Picks 10 at random from that list and presents them in the UI one at a time.

Selection strategy: Prioritize Outliers first. Pick all chapters where `is_outlier: true` first (up to 10), then fill remaining slots with non-outliers at random. This ensures high-delta chapters get human review.

UI per chapter:
- Displays: book title, chapter number, `listen_url`, and pipeline-generated `exact_audio_skip_seconds`
- If the chapter is an Outlier, display a warning: `[OUTLIER: delta +6.59s]`
- Audio player that plays from the detected skip timestamp
- Button to "play from 5 seconds before" the skip timestamp
- Approve and Deny buttons at the bottom

On Approve: mark the entry verified via `repository.mark_verified()` and move to the next chapter. 

On Deny: **Stop the verification process immediately.** Output a message: "Verification failed: Pipeline produced incorrect result. File a bug and fix the pipeline before rerunning." Do not allow the contributor to proceed. The entire batch is rejected.

If fewer than 10 chapters are available, verify all of them, then display: "Only <N> chapters verified (need 10 minimum). Run `python verify.py --override` to create a PR anyway. 10 verified entries ensures quality — proceeding with fewer is not recommended."

If 10 or more chapters are approved (or `--override` is used with any number >= 1), summarize the verification: "Verified <N> chapters from <M> total new entries. Ready to submit." Offer: "Create PR now? (y/n)". If yes, commit `repository.json` and create a PR via `gh pr create` with an auto-generated description summarizing the contribution (e.g., "Add <N> verified chapters from <book titles>"). If no, print git/gh commands for the contributor to run manually.

## Acceptance criteria

- [ ] Reads `chapters_to_verify.json` to identify chapters from this run
- [ ] Prioritizes Outliers; selects up to 10 chapters with Outliers first
- [ ] Displays chapter title, `listen_url`, `exact_audio_skip_seconds`, and `[OUTLIER: delta ...]` if applicable
- [ ] Approve: marks verified via `repository.mark_verified()`, moves to next chapter
- [ ] Deny: stops immediately with error message "Verification failed: Pipeline produced incorrect result. File a bug and fix the pipeline before rerunning."
- [ ] Exits cleanly after 10 approvals
- [ ] If fewer than 10 chapters available: verifies all, displays "Only <N> chapters verified (need 10 minimum). Run `python verify.py --override` to proceed anyway. 10 verified entries ensures quality."
- [ ] `--override` flag allows PR creation with fewer than 10 verified chapters (but >= 1)
- [ ] On success, offers "Create PR now? (y/n)" and commits + creates PR via gh, or prints git/gh commands
- [ ] Contributors cannot pre-select which entries to verify
- [ ] Runs a local web server with browser UI for audio playback and approval

## Blocked by

- 00-setup-and-fixtures.md (for test environment)
- 01-repository-module.md
- 03-audio-fetcher.md
