## Testing

Any change that touches logic (pipeline stages, timestamp detection, batch processing, output formatting) must have tests written or updated using the TDD skill (red → green → refactor) before committing. Script or CLI changes that are purely cosmetic do not require tests, but any logic extracted from scripts must be tested.

---

## Git workflow

At every logical stopping point — after a feature is working, tests pass, or a doc/bug fix is complete — commit and push changes without waiting to be asked. Use clear conventional commit messages.

---

## Documentation — non-negotiable

**Documentation must be updated in the same commit as the code change. Never commit code that makes docs incorrect.**

Before marking any task done, verify:

- `docs/ARCHITECTURE.md` — updated if any module, data flow, pipeline stage, schema, or output format changed
- `docs/CONTEXT.md` — updated if any domain term, stage description, or system behaviour changed
- `docs/adr/` — new ADR added (or existing updated) if an architectural decision was made or reversed

If you are unsure whether a doc needs updating, check it. Stale documentation is treated as a bug. A codebase where docs and code disagree is actively harmful — it misleads future agents and makes the system harder to change safely.

---

## Architecture

When making architectural decisions, read `docs/agents/philosophy.md` first.

## Agent skills

### Issue tracker

Issues are tracked as markdown files under `docs/.scratch/`. See `docs/agents/issue-tracker.md` for the full convention.

### Domain docs

Single-context layout — `docs/ARCHITECTURE.md` (how it works) + `docs/CONTEXT.md` (domain glossary) + `docs/adr/` (decisions).
