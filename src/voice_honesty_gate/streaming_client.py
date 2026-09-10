"""Live-call client for AssemblyAI's Streaming Speech-to-Text product.

This is a DIFFERENT AssemblyAI product from the one `live_client.py`
targets. `live_client.py` is the Voice Agent API
(`agents.assemblyai.com`, `tool.call`/`tool.result`/`transcript.agent`
events, its own `tools` schema). This module is the plain Streaming
Speech-to-Text product (`streaming.assemblyai.com/v3/ws`, `Begin`/`Turn`/
`Termination` events, no tool schema at all) -- the one `cli.py`'s `live`
subcommand actually needs, because the honesty check's tool-call evidence
for a live microphone demo comes from `--tool-log` (this repo's own file),
not from anything AssemblyAI's streaming socket sends.

Endpoint, auth, audio format, and message shapes below are quoted and
cited in full in `docs/LIVE_MIC.md` (fetched from assemblyai.com/docs on
2026-09-09); this module does not invent anything not sourced there.

  WebSocket   wss://streaming.assemblyai.com/v3/ws?sample_rate=<rate>
  Auth        header "Authorization: <api key>" (no "Bearer" prefix)
  Audio in    raw PCM16LE mono, sent as binary WebSocket frames, 4096
              bytes/chunk (docs' own example chunk size)
  Turn event  {"type": "Turn", "turn_order": N, "end_of_turn": bool,
               "transcript": "...", "words": [...]}
  End session {"type": "Terminate"}

Uses the third-party `websockets` package (sync client,
`websockets.sync.client.connect`) rather than `live_client.py`'s
hand-rolled RFC 6455 socket code -- the CLI's `live` mode goal explicitly
calls for the `websockets` package, and a sync client keeps this module's
control flow (read a Turn, print it, maybe fire the honesty check, repeat)
as plain and inspectable as the rest of this repo's synchronous style.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Iterator

from voice_honesty_gate.errors import NoApiKeyError
from voice_honesty_gate.live_client import DEFAULT_KEY_PATH, read_api_key

try:
    from websockets.sync.client import connect as _ws_connect
    from websockets.exceptions import ConnectionClosed as _WSConnectionClosed
except ImportError as exc:  # pragma: no cover - exercised only if the dep truly is absent
    raise ImportError(
        "streaming_client.py needs the 'websockets' package (pip install websockets) for the "
        "live microphone/streaming path. Fixture-mode `vhg check` does not need it."
    ) from exc

STREAMING_WS_URL = "wss://streaming.assemblyai.com/v3/ws"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHUNK_BYTES = 4096  # docs' own worked-example chunk size, see docs/LIVE_MIC.md

# how long to keep listening for the last Turn/Termination after sending
# Terminate, per docs/LIVE_MIC.md's quoted "keep the connection open long
# enough to receive the last final."
_DRAIN_SECONDS = 5.0


class StreamingTurn:
    """One `Turn` event, trimmed to the fields this build reads."""

    __slots__ = ("transcript", "end_of_turn", "turn_order", "raw")

    def __init__(self, transcript: str, end_of_turn: bool, turn_order: int, raw: dict) -> None:
        self.transcript = transcript
        self.end_of_turn = end_of_turn
        self.turn_order = turn_order
        self.raw = raw


def build_ws_url(sample_rate: int = DEFAULT_SAMPLE_RATE) -> str:
    """Default-PCM16 connection URL: `sample_rate` set, `encoding` omitted
    (docs' "Default: mono 16-bit PCM" line -- see docs/LIVE_MIC.md's
    "least-certain fact #1")."""
    return f"{STREAMING_WS_URL}?sample_rate={int(sample_rate)}"


def stream_transcribe(
    audio_chunks: Iterable[bytes],
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    api_key: str | None = None,
    key_path: Path | str = DEFAULT_KEY_PATH,
    ws_url: str | None = None,
    on_turn: Callable[[StreamingTurn], None] | None = None,
    on_raw_event: Callable[[dict], None] | None = None,
) -> Iterator[StreamingTurn]:
    """Open a real AssemblyAI Streaming Speech-to-Text WebSocket session,
    send every chunk in `audio_chunks` as a binary frame, and yield every
    `Turn` event the server sends back (partial and final alike -- callers
    filter on `.end_of_turn`). Sends `{"type": "Terminate"}` once
    `audio_chunks` is exhausted and drains remaining frames for up to
    `_DRAIN_SECONDS` before returning.

    Raises NoApiKeyError before opening any socket if no key is available,
    the same fail-fast contract `live_client.py` and
    `pre_recorded_client.py` already use.

    Sending and receiving happen concurrently (a background thread drains
    `audio_chunks` and calls `ws.send()`; this generator's own thread calls
    `ws.recv()` in a loop) so `Turn` events are yielded as they arrive
    instead of only after every chunk has been sent -- required for the
    microphone path to print/react in real time rather than at the end of
    the whole capture. `websockets.sync`'s connection object supports one
    thread sending while another thread receives (its own internal
    `recv_events_thread` already does exactly that); only concurrent
    `recv()` calls from two threads are disallowed, and this module never
    does that.
    """
    key = api_key or read_api_key(key_path)
    if not key:
        raise NoApiKeyError(f"no AssemblyAI API key found at {key_path!s}")

    url = ws_url if ws_url is not None else build_ws_url(sample_rate)
    with _ws_connect(url, additional_headers={"Authorization": key}) as ws:
        send_error: list[BaseException] = []
        send_done = threading.Event()

        def _sender() -> None:
            try:
                for chunk in audio_chunks:
                    ws.send(chunk)  # bytes -> binary frame, per docs/LIVE_MIC.md
                ws.send(json.dumps({"type": "Terminate"}))
            except BaseException as exc:  # noqa: BLE001 - surfaced to the main thread below
                send_error.append(exc)
            finally:
                send_done.set()

        sender_thread = threading.Thread(target=_sender, daemon=True)
        sender_thread.start()

        drain_deadline: float | None = None
        while True:
            if send_done.is_set() and drain_deadline is None:
                drain_deadline = time.monotonic() + _DRAIN_SECONDS
            if drain_deadline is not None and time.monotonic() >= drain_deadline:
                break

            try:
                raw = ws.recv(timeout=0.25)
            except TimeoutError:
                continue
            except _WSConnectionClosed:
                break

            event = json.loads(raw)
            if on_raw_event is not None:
                on_raw_event(event)  # every documented event (Begin/Turn/Termination), for a full session receipt
            etype = event.get("type")
            if etype == "Turn":
                turn = StreamingTurn(
                    transcript=str(event.get("transcript", "")),
                    end_of_turn=bool(event.get("end_of_turn", False)),
                    turn_order=int(event.get("turn_order", 0)),
                    raw=event,
                )
                if on_turn is not None:
                    on_turn(turn)
                yield turn
            elif etype == "Termination":
                break
            # "Begin" and any other documented event type is read-and-ignored
            # on purpose (this build only needs Turn text and Termination).

        sender_thread.join(timeout=1.0)
        if send_error:
            raise send_error[0]
