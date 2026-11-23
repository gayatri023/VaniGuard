"""Audio intake. Audio never touches the DB or logs; temp files die in the context manager."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

ALLOWED_MIME = {"audio/webm", "audio/mp4", "audio/ogg", "audio/wav", "audio/x-wav", "audio/wave"}
MAX_UPLOAD_BYTES = 3_000_000
MAX_SECONDS = 15.5
MIN_SECONDS = 0.3


class AudioError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def base_mime(mime: str) -> str:
    return mime.split(";")[0].strip().lower()


async def to_wav16k(data: bytes) -> bytes:
    """Transcode anything ffmpeg understands (Chrome webm/opus, iOS mp4/aac, ogg, wav) to 16 kHz mono WAV."""
    with tempfile.TemporaryDirectory(prefix="vani-") as d:  # removed on every path, including errors
        src, dst = Path(d) / "in.bin", Path(d) / "out.wav"
        src.write_bytes(data)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(src),
                "-t", "16", "-ar", "16000", "-ac", "1", "-f", "wav", str(dst),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )  # fmt: skip
        except FileNotFoundError as exc:
            raise AudioError("ffmpeg_missing") from exc
        try:
            await asyncio.wait_for(proc.communicate(), timeout=10)
        except TimeoutError as exc:
            proc.kill()
            raise AudioError("transcode_timeout") from exc
        if proc.returncode != 0 or not dst.exists():
            raise AudioError("transcode_failed")
        wav = dst.read_bytes()
    seconds = max(0, len(wav) - 44) / 32000
    if seconds > MAX_SECONDS:
        raise AudioError("too_long")
    if seconds < MIN_SECONDS:
        raise AudioError("too_short")
    return wav
