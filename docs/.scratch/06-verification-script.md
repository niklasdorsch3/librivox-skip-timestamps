Status: ready-for-agent

## What to build

The `verify.py` Verification Script — run by a contributor after `main.py` to confirm 10 chapters before submitting a PR. Picks chapters at random from entries in `repository.json` that are not yet verified, presents each one interactively, and writes `verified: true` on confirmation via `repository.mark_verified()`.

Interaction per chapter:
```
Chapter 3/10: The Art of War — Chapter 1
Listen: https://librivox.org/...
Pipeline result: 14.80s
Does this sound correct? [y/n]:
```

On `y`: mark verified, move to next. On `n`: pick a replacement at random. Continue until 10 are confirmed or all unverified entries are exhausted.

If fewer than 10 unverified entries exist, verify all of them and inform the contributor they need to run more books before the PR will pass CI.

## Acceptance criteria

- [ ] Picks unverified entries at random from `repository.json`
- [ ] Displays chapter title, `listen_url`, and `exact_audio_skip_seconds` for each
- [ ] `y` writes `verified: true` via `repository.mark_verified()`
- [ ] `n` picks a replacement chapter at random
- [ ] Exits cleanly after 10 confirmations
- [ ] If fewer than 10 unverified entries exist, verifies all and prints a warning that more books are needed
- [ ] Contributors cannot pre-select which entries to verify

## Blocked by

- 01-repository-module.md
- 03-audio-fetcher.md
