"""Offline tests for `cli.py live` mode / `live_session.py`. No network
access, no AssemblyAI key: a local `websockets` server stands in for
AssemblyAI's Streaming Speech-to-Text endpoint, emitting the exact
documented message shapes (Begin / Turn / Termination, see
docs/LIVE_MIC.md) so `streaming_client.stream_transcribe`'s real client
code is exercised end to end -- only the far side of the socket is fake,
not this repo's own code.

The audio driving both cases is a real WAV of Windows-synthesized speech
("I have cancelled your flight, all done", see
scripts/synthesize_wav.ps1 and tests/fixtures/audio/live_mic_demo.wav) fed
through the real `wav_chunks` reader and the real WebSocket send path; the
fake server does not run any actual speech-to-text on those bytes (that
would need the real paid AssemblyAI service) -- it plays back a canned
transcript matching the WAV's spoken sentence, which is the honest, stated
boundary of what an offline test can prove. `LIVE_MIC_RECEIPT.md` is the
one real AssemblyAI run that closes the rest of that gap.
"""

from __future__ import annotations

import json
import threading

import pytest
import websockets.sync.server as ws_server

import voice_honesty_gate  # noqa: F401
from voice_honesty_gate.audio_capture import wav_chunks
from voice_honesty_gate.live_session import run_live_session
from voice_honesty_gate.tool_log import load_tool_log_events

WAV_PATH = "tests/fixtures/audio/live_mic_demo.wav"
CANNED_TRANSCRIPT = "I have cancelled your flight, all done"


class _FakeAssemblyAIStreamingServer:
    """A local websockets server that plays the documented Begin/Turn/
    Termination sequence back at whatever client connects, regardless of
    the audio bytes it receives (this is a transport-and-message-shape
    fake, not a speech-to-text engine)."""

    def __init__(self, transcript: str) -> None:
        self.transcript = transcript
        self._server: ws_server.Server | None = None
        self._thread: threading.Thread | None = None

    def _handler(self, connection: ws_server.ServerConnection) -> None:
        connection.send(json.dumps({"type": "Begin", "id": "sess_fake", "expires_at": 0}))
        terminated = False
        for raw in connection:
            if isinstance(raw, (bytes, bytearray)):
                continue  # an audio chunk -- the fake server does not transcribe it, see module docstring
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "Terminate":
                terminated = True
                break
        if terminated:
            connection.send(
                json.dumps(
                    {
                        "type": "Turn",
                        "turn_order": 0,
                        "end_of_turn": True,
                        "transcript": self.transcript,
                        "words": [],
                    }
                )
            )
            connection.send(json.dumps({"type": "Termination", "audio_duration_seconds": 3, "session_duration_seconds": 3}))

    def __enter__(self) -> str:
        self._server = ws_server.serve(self._handler, "127.0.0.1", 0)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._server.socket.getsockname()[:2]
        return f"ws://{host}:{port}"

    def __exit__(self, *exc_info) -> None:
        assert self._server is not None
        self._server.shutdown()
        self._thread.join(timeout=5)


def test_live_session_holds_on_a_spoken_completion_claim_with_no_tool_log():
    """The central live-mode proof: real WAV audio streamed through the
    real send path, a spoken false-completion claim comes back from the
    (fake) streaming server, no tool log given -> HOLD /
    FALSE_COMPLETION_CLAIM, matching the goal's stated default."""
    with _FakeAssemblyAIStreamingServer(CANNED_TRANSCRIPT) as url:
        sample_rate, chunks = wav_chunks(WAV_PATH, pace=False)
        printed: list[str] = []
        receipt = run_live_session(
            chunks,
            sample_rate,
            tool_log_events=load_tool_log_events(None),
            session_id="test-live-hold",
            api_key="fake-test-key-not-sent-anywhere-real",
            ws_url=url,
            print_fn=printed.append,
        )

    assert receipt["decision"] == "HOLD"
    assert receipt["findings"][0]["code"] == "FALSE_COMPLETION_CLAIM"
    assert receipt["claim_text"] == CANNED_TRANSCRIPT
    assert receipt["claim_detected_at"] is not None
    assert receipt["transcript_turns"][0]["text"] == CANNED_TRANSCRIPT
    assert any("completion claim detected" in line for line in printed)
    assert any(CANNED_TRANSCRIPT in line for line in printed)  # each final turn printed as it arrives


def test_live_session_goes_when_a_matching_tool_log_backs_the_claim(tmp_path):
    """Same spoken claim, same fake server -- but this time a tool log
    records a confirmed, non-error tool result for the cancellation, so the
    ported check finds backing evidence and the session goes GO."""
    tool_log_path = tmp_path / "tool_log.json"
    tool_log_path.write_text(
        json.dumps(
            {
                "tool_calls": [
                    {
                        "name": "cancel_flight",
                        "arguments": {"flight": "DAD-101"},
                        "result": '{"status": "cancelled"}',
                        "is_error": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with _FakeAssemblyAIStreamingServer(CANNED_TRANSCRIPT) as url:
        sample_rate, chunks = wav_chunks(WAV_PATH, pace=False)
        receipt = run_live_session(
            chunks,
            sample_rate,
            tool_log_events=load_tool_log_events(str(tool_log_path)),
            session_id="test-live-go",
            api_key="fake-test-key-not-sent-anywhere-real",
            ws_url=url,
            print_fn=lambda _line: None,
        )

    assert receipt["decision"] == "GO"
    assert receipt["findings"] == []
    assert receipt["tool_log_call_count"] == 1


def test_load_tool_log_events_defaults_to_empty_list():
    assert load_tool_log_events(None) == []


def test_load_tool_log_events_rejects_a_malformed_file(tmp_path):
    from voice_honesty_gate.errors import MalformedTranscriptError

    bad = tmp_path / "bad.json"
    bad.write_text('{"not_tool_calls": []}', encoding="utf-8")
    with pytest.raises(MalformedTranscriptError):
        load_tool_log_events(str(bad))
