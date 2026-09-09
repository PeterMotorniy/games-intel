from __future__ import annotations

import tempfile
from pathlib import Path

from games_intel.adapters.youtube.audio import cleanup_downloaded_audio


def test_cleanup_downloaded_audio_removes_gi_temp_dir() -> None:
    target_dir = Path(tempfile.mkdtemp(prefix="gi-yt-audio-"))
    clip = target_dir / "clip.wav"
    clip.write_bytes(b"x")
    cleanup_downloaded_audio(str(clip))
    assert not clip.exists()
    assert not target_dir.exists()


def test_cleanup_downloaded_audio_ignores_other_paths() -> None:
    target_dir = Path(tempfile.mkdtemp(prefix="other-audio-"))
    clip = target_dir / "clip.wav"
    clip.write_bytes(b"x")
    try:
        cleanup_downloaded_audio(str(clip))
        assert clip.exists()
    finally:
        clip.unlink(missing_ok=True)
        target_dir.rmdir()


def test_cleanup_downloaded_audio_ignores_file_uri() -> None:
    cleanup_downloaded_audio("file://clip.wav")
