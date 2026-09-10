"""Audio sources for `cli.py live` mode: a real microphone, or a WAV file
standing in for one (so the same streaming code path is exercisable
without a microphone present -- tests and CI use this path).

Both `mic_chunks` and `wav_chunks` yield raw PCM16LE mono bytes, paced to
real time (each chunk is yielded no faster than the wall-clock duration of
audio it represents), and both report the sample rate they captured/read
at -- `cli.py` passes that straight to
`streaming_client.build_ws_url(sample_rate=...)` so the query parameter
always matches the bytes actually being sent (see docs/LIVE_MIC.md).

`mic_chunks` needs the `sounddevice` package (PortAudio bindings). It is
imported lazily, inside the function, so `--from-wav` (used by every test
in this repo, and by any machine with no microphone) never needs
`sounddevice` importable at all.
"""

from __future__ import annotations

import queue
import time
import wave
from pathlib import Path
from typing import Iterator

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHUNK_FRAMES = 2048  # frames, not bytes; *2 bytes/frame (16-bit) = 4096 bytes, matching docs' example


def wav_chunks(
    path: Path | str,
    chunk_frames: int = DEFAULT_CHUNK_FRAMES,
    pace: bool = True,
) -> tuple[int, Iterator[bytes]]:
    """Read `path` (must be mono 16-bit PCM WAV) and return
    (sample_rate, chunk_iterator). Each chunk is `chunk_frames` frames of
    raw PCM16LE bytes; `pace=True` (default) sleeps between yields so the
    file streams at real-time speed, matching what a live microphone would
    hand the WebSocket -- `--from-wav` is meant to exercise the exact same
    timing-sensitive code path as `mic_chunks`, not just the same bytes.
    """
    wf = wave.open(str(path), "rb")
    if wf.getsampwidth() != 2 or wf.getnchannels() != 1:
        wf.close()
        raise ValueError(
            f"{path!s} is not mono 16-bit PCM (got {wf.getnchannels()} channel(s), "
            f"{wf.getsampwidth() * 8}-bit) -- streaming_client.py expects the AssemblyAI-default "
            "PCM16 mono format documented in docs/LIVE_MIC.md"
        )
    sample_rate = wf.getframerate()

    def _iter() -> Iterator[bytes]:
        try:
            chunk_seconds = chunk_frames / sample_rate
            while True:
                data = wf.readframes(chunk_frames)
                if not data:
                    break
                if pace:
                    time.sleep(chunk_seconds)
                yield data
        finally:
            wf.close()

    return sample_rate, _iter()


def mic_chunks(
    seconds: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    chunk_frames: int = DEFAULT_CHUNK_FRAMES,
) -> tuple[int, Iterator[bytes]]:
    """Capture `seconds` of real microphone audio via `sounddevice`,
    yielding raw PCM16LE mono chunks as they are captured (paced by
    PortAudio's own callback timing -- no artificial sleep needed, unlike
    `wav_chunks`). Returns (sample_rate, chunk_iterator).

    Raises ImportError with an actionable message if `sounddevice` is not
    installed (this repo's CLI installs it on first `live` run without
    `--from-wav`; see cli.py).
    """
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise ImportError(
            "live microphone mode needs the 'sounddevice' package: pip install sounddevice "
            "(free, no API key). Use --from-wav <file.wav> to exercise the same code path "
            "without a microphone."
        ) from exc

    q: "queue.Queue[bytes | None]" = queue.Queue()
    frames_wanted = int(seconds * sample_rate)
    frames_captured = 0

    def _callback(indata, frames, time_info, status) -> None:  # noqa: ANN001 - sounddevice's own signature
        nonlocal frames_captured
        q.put(bytes(indata))
        frames_captured += frames
        if frames_captured >= frames_wanted:
            raise sd.CallbackStop

    def _iter() -> Iterator[bytes]:
        stream = sd.RawInputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=chunk_frames,
            callback=_callback,
        )
        with stream:
            while stream.active or not q.empty():
                try:
                    chunk = q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if chunk is None:
                    break
                yield chunk

    return sample_rate, _iter()
