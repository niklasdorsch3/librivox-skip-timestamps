Status: ready-for-agent

## What to build

A contribution validation script (`validate_contribution.py`) and GitHub Actions workflow that runs on every pull request. The script diffs `repository.json` against the base branch and checks the contribution rules. The workflow posts a summary as a PR comment, flagging any rule violations as warnings. Violations do not block merge — they inform the reviewer.

Rules (warnings only):
1. More than 100 new chapter entries — warning with count
2. Fewer than 10 verified entries — warning with count and suggestion to run more books or use `--override`

## Acceptance criteria

- [ ] GitHub Actions workflow runs `validate_contribution.py` on every PR to `main`
- [ ] Script compares `repository.json` in the PR against the base branch version
- [ ] Script counts new entries (not in base branch) and verified entries among them
- [ ] Posts a comment on the PR with:
  - Total new entries and verified count (always shown)
  - Warning if > 100 entries: "⚠️ More than 100 entries (<N> found) — consider splitting into smaller PRs"
  - Warning if < 10 verified: "⚠️ Fewer than 10 verified entries (<N> found) — run more books or use `--override`"
  - ✓ checkmark if both rules satisfied
- [ ] Both rules are checked independently
- [ ] Violations are warnings only; they do not block merge
- [ ] Tests cover all boundary cases: 100/101 entries, 10/9 verified, both warnings at once, edge case with no changes

## Blocked by

- 00-setup-and-fixtures.md (for test environment)
- 01-repository-module.md
