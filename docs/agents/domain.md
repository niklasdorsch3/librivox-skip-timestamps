# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — domain glossary defining all key terms
- **`docs/adr/`** — read ADRs that touch the area you're about to work in

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT.md
├── ARCHITECTURE.md
├── docs/adr/
│   └── 0001-*.md
└── src/   (or top-level .py scripts)
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

Key terms to be precise about:
- **Pipeline** not "script" or "process"
- **Stage** not "step" or "phase"
- **Disclaimer** not "intro" or "preamble"
- **Anchor Word** not "boundary word" or "last word"
- **T_approx / T_exact** — use these names, not "rough timestamp" or "final timestamp"
- **Repository** — the output JSON file, not the git repo
- **Checkpoint** — the SQLite resume state, not a git tag
- **Verification Script** not "tune.py" or "tuning script"
- **Contribution** — a PR batch of up to 100 timestamps, not just "a PR" or "a batch"
- **Verified Entry** — a chapter confirmed by a human, not just "checked" or "validated"

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0002 (local-only inference) — but worth reopening because…_
