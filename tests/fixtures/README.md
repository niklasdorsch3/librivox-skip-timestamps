# Test Fixtures

## sample_chapter.mp3

**Source:** LibriVox recording of *The Art of War* by Sun Tzu (LibriVox project ID 119)  
**Chapter:** "01 - Laying Plans / 02 - Waging War"  
**Archive URL:** `https://www.archive.org/download/art_of_war_librivox/art_of_war_01-02_sun_tzu_64kb.mp3`  
**License:** Public domain (LibriVox recordings are released into the public domain)

**Selection rationale:**  
- Opens with the standard LibriVox Disclaimer (spoken before the literary text begins), making it suitable for testing disclaimer boundary detection.
- The file has been trimmed to approximately the first 25 seconds, which captures the full Disclaimer and the start of the literary content.
- At 64 kbps, this represents ~200 KB of audio — small enough for fast test runs.

**Approximate disclaimer boundary:** ~13–15 seconds into the recording.

## Replacing the fixture

If this fixture needs to be updated (e.g. the archive URL becomes unavailable, or a different chapter is needed):

1. Find a LibriVox chapter via the LibriVox API:
   `https://librivox.org/api/feed/audiobooks?title=<book>&format=json`
2. Locate the MP3 URL from the chapter's RSS feed or archive.org listing.
3. Download the first ~25 seconds using a Range request (at 64 kbps: `Range: bytes=0-200000`).
4. Confirm the file starts with the spoken Disclaimer before committing.
5. Update this README with the new source URL and selection rationale.
