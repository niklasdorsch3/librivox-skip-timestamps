"""Audio fetcher — downloads a LibriVox chapter to a temporary file."""

import os
import tempfile
from contextlib import contextmanager
from typing import Iterator

import requests

DOWNLOAD_TIMEOUT = 60  # seconds
MAX_RETRIES = 1


class AudioFetchError(Exception):
    """Raised when a chapter audio file cannot be downloaded after all retries."""


class AudioFetcher:
    @staticmethod
    @contextmanager
    def fetch(
        listen_url: str,
        session: requests.Session | None = None,
    ) -> Iterator[str]:
        """Download listen_url to a temp file and yield its path.

        Retries once on transient network errors before raising AudioFetchError.
        The temp file is always deleted on context exit.
        """
        if session is None:
            session = requests.Session()

        fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

        try:
            _download(listen_url, tmp_path, session)
            yield tmp_path
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _download(url: str, dest: str, session: requests.Session) -> None:
    """Download url to dest, retrying once on transient RequestException."""
    last_error: Exception | None = None
    for _ in range(MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return
        except requests.exceptions.RequestException as exc:
            last_error = exc
    raise AudioFetchError(f"Failed to download {url}: {last_error}") from last_error
