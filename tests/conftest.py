"""Shared pytest configuration — sets up static ffmpeg path for pydub."""

try:
    import static_ffmpeg

    static_ffmpeg.add_paths()
except ImportError:
    pass
