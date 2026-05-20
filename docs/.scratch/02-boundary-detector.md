Status: ready-for-agent

## What to build

A `BoundaryDetector` module that owns the full contract of "given a transcript, return where the Disclaimer ends." It encapsulates the Ollama HTTP call, retry-once logic, JSON parsing, and the `NoDisclaimer` vs `AnchorWord` branching — nothing leaks to the caller.

Exposes a single function: `detect_boundary(transcript: str) -> BoundaryResult`.

`BoundaryResult` has two states:
- `NoDisclaimer` — LLM returned `null` for the anchor word; chapter has no Disclaimer
- `AnchorWord(word: str, confidence: float)` — LLM identified the last Disclaimer word

On malformed JSON: retry the LLM call once. If still malformed on the second attempt, raise a typed exception. On `NoDisclaimer`, do not raise — it is a clean result.

The Ollama endpoint and model are configurable via environment variables (`OLLAMA_MODEL`, defaulting to `llama3.2:3b`).

## Acceptance criteria

- [ ] `detect_boundary` returns `AnchorWord` when LLM responds with a valid word
- [ ] `detect_boundary` returns `NoDisclaimer` when LLM responds with `null`
- [ ] Malformed JSON on first attempt triggers exactly one retry
- [ ] Malformed JSON on both attempts raises a typed `BoundaryDetectionError`
- [ ] Module is testable with a fake HTTP adapter — no running Ollama instance required
- [ ] `OLLAMA_MODEL` env var controls which model is used
- [ ] All four outcomes above are covered by tests

## Blocked by

- 00-setup-and-fixtures.md (for test environment: ollama)
