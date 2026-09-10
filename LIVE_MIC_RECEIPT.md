# Live Mic Receipt — voice-honesty-gate

Real end-to-end AssemblyAI **Streaming Speech-to-Text** call, 2026-09-09.
This is a different AssemblyAI product from the one `LIVE_RECEIPT.md`
proved (that receipt used the pre-recorded transcription REST API; this
one uses the real-time WebSocket streaming API — endpoint, auth, message
shapes, and pricing all cited with URLs in `docs/LIVE_MIC.md`, fetched
live this same session). It is the one real call the goal's step 5
required: `vhg live --from-wav <clip>`, audio in over a real streaming
WebSocket, a spoken claim out, the ported honesty check run on it.

## What was sent

```
python -m voice_honesty_gate.cli live --from-wav tests/fixtures/audio/live_mic_demo.wav
```

- Audio: `tests/fixtures/audio/live_mic_demo.wav` — 16 kHz mono 16-bit PCM,
  3.22 seconds, synthesized by Windows `System.Speech`
  (`scripts/synthesize_wav.ps1`) speaking **"I have cancelled your flight,
  all done"** — a spoken false completion claim with, deliberately, no
  `--tool-log` given (the goal's stated default: an empty tool log).
- Connection: `wss://streaming.assemblyai.com/v3/ws?sample_rate=16000`
  (`streaming_client.build_ws_url`), header `Authorization: <key>` (no
  `Bearer` prefix), `encoding` query parameter omitted (default mono
  16-bit PCM, per `docs/LIVE_MIC.md`).
- Audio bytes: sent as raw PCM16LE binary WebSocket frames, 4096-byte
  chunks (`audio_capture.wav_chunks`, `chunk_frames=2048` -> 4096 bytes at
  16-bit), paced to real time (`pace=True`, the default).
- `{"type": "Terminate"}` sent once the WAV was exhausted.

## What came back (real AssemblyAI response, verbatim from the saved receipt)

Session opened with model `universal-3-5-pro` (AssemblyAI's account
default — no `speech_model` query parameter was sent, so this is
AssemblyAI's own choice, not this build's):

```json
{"type": "Begin", "id": "3a28fcf2-1c50-4c2a-a3ab-b83d691c5105", "expires_at": 1788954128,
 "configuration": {"model": "universal-3-5-pro", "mode": "balanced", "api_version": "2025-05-12", ...}}
```

Three `Turn` events followed (two partials, `end_of_turn: false`, then one
final): the final one carries AssemblyAI's own transcribed text, matching
the spoken script word-for-word:

```json
{"type": "Turn", "turn_order": 0, "end_of_turn": true, "end_of_turn_confidence": 1.0,
 "transcript": "I have cancelled your flight, all done.",
 "utterance": "I have cancelled your flight, all done."}
```

Then:

```json
{"type": "Termination", "audio_duration_seconds": 3, "session_duration_seconds": 4}
```

Full raw message list (Begin, SpeechStarted, all three Turns, Termination)
is saved verbatim in
`live_sessions/live-fromwav-live_mic_demo_20260909_154211.json`'s
`raw_server_messages` field — nothing here is retyped from memory.

## Decision

```
[15:42:10] turn 0: I have cancelled your flight, all done.
[15:42:10] completion claim detected -> decision: HOLD
[15:42:10]   FALSE_COMPLETION_CLAIM: final spoken claim asserts completion but no tool was ever called in this session
session receipt written to live_sessions\live-fromwav-live_mic_demo_20260909_154211.json
```

Exit code: `2` (HOLD, fails closed — same convention `vhg check` uses).
`vhg live`'s decision came from the exact same, unforked
`voice_rules.check_voice_false_completion_claim` fixture-mode `vhg check`
already uses — the only new code in this build is the audio-capture and
streaming-transport path that gets a real spoken claim into that same
check.

**Not run as a second live call** (the goal named ONE real run): the
matching GO case, where `--tool-log` backs the same claim with a confirmed
tool result, is proven offline instead, against a local fake streaming
server replaying the exact real AssemblyAI transcript text captured above
— see `tests/test_live_mode.py::test_live_session_goes_when_a_matching_tool_log_backs_the_claim`
and `LIVE_RECEIPT.md`'s own pre-recorded-API precedent for the same
GO/HOLD pairing pattern.

## Cost

From `docs/LIVE_MIC.md`'s pricing quote (`https://www.assemblyai.com/pricing`):

> **Universal-3.5 Pro Realtime** (`u3-rt-pro`): **$0.45/hr** ... "Session
> duration, not audio duration."

This call's own `Begin` event confirms `model: "universal-3-5-pro"`, so
the $0.45/hr rate applies, billed on `session_duration_seconds: 4` (not
`audio_duration_seconds: 3`, per the quoted billing rule):

```
4 seconds x ($0.45 / 3600 seconds) = $0.0005
```

Well inside a trivial one-call budget; no free-tier concurrency limit
(5 streams/min) was approached (one stream, one call).

## What this proves and what it does not

**Proves**: a real, live AssemblyAI Streaming Speech-to-Text WebSocket
session — `streaming_client.py`'s real `websockets` client code, not a
stub — transcribed real spoken audio, and `vhg live`'s session loop fed
that real transcript into the same unforked honesty check `vhg check`
already uses, printing the HOLD decision the moment the claim appeared and
saving the full raw exchange.

**Does not prove**: a live microphone capture itself (`audio_capture.mic_chunks`,
the `sounddevice`-based path) was not exercised against AssemblyAI in this
receipt — `--from-wav` was used instead, per the goal's own design ("so the
same code path can be driven from a file when no microphone is present").
`mic_chunks` and `wav_chunks` share every line of code downstream of
"yield raw PCM16LE bytes at real-time pace" (`streaming_client.stream_transcribe`
does not know or care which produced the bytes), so this is a narrow,
named gap, not a hidden one.
