# Issue tracker: Local Markdown

Issues and PRDs for this repo live as markdown files in `docs/.scratch/`.

## Conventions

- PRDs are flat files: `docs/.scratch/<feature-slug>-prd.md`
- Implementation issues are: `docs/.scratch/<feature-slug>-<NN>-<slug>.md`
- Triage state is recorded as a `Status:` line near the top of each file (see `triage-labels.md` for the role strings)
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `docs/.scratch/` following the naming convention above.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.
