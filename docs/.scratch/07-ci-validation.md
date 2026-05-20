Status: ready-for-agent

## What to build

A contribution validation script (`validate_contribution.py`) and GitHub Actions workflow that runs on every pull request. The script diffs `repository.json` against the base branch (`git show origin/main:repository.json`) and enforces the contribution rules. The workflow fails the PR with a clear message if either rule is violated.

Rules:
1. No more than 100 new chapter entries in the PR
2. At least 10 of the new entries have `"verified": true`

## Acceptance criteria

- [ ] GitHub Actions workflow runs `validate_contribution.py` on every PR
- [ ] Script fetches the base branch version via `git show origin/main:repository.json`
- [ ] Exactly 100 new entries passes; 101 fails with a clear error message
- [ ] Exactly 10 new verified entries passes; 9 fails with a clear error message
- [ ] Both rules are checked independently — output states which rule(s) failed
- [ ] Tests cover all boundary cases: 100/101 entries, 10/9 verified, both failing at once

## Blocked by

- 01-repository-module.md
