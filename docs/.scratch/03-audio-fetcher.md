Status: ready-for-agent

## What to build

An `AudioFetcher` module that downloads a LibriVox chapter to a temporary file and cleans up after use. Used as a context manager so the temp file is always deleted — on success or failure — without callers managing cleanup.

Interface: `with AudioFetcher.fetch(listen_url) as path` — yields the local path to the downloaded file.

Handles download retries and timeouts internally. The caller never sees a partial download.

## Acceptance criteria

- [ ] Context manager yields a valid local file path on successful download
- [ ] Temp file is deleted on context exit regardless of whether an exception was raised
- [ ] A failed download (network error, timeout) raises a typed `AudioFetchError`
- [ ] Retry logic is applied before raising (at least one retry on transient errors)
- [ ] No temp files are left on disk after any code path

## Blocked by

None — can start immediately.
