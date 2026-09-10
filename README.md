# Voice Honesty Gate

A voice-agent honesty gate for the AssemblyAI Voice Agent Hackathon
(lablab.ai, Sep 1-30 2026). Ports [relay-gate](../relay-gate/)'s
`FALSE_COMPLETION_CLAIM` check — already tested on 7,293 real
coding-agent trajectories — from reading a text transcript to reading a
live AssemblyAI Voice Agent WebSocket transcript. A spoken "done" that no
tool call backs up gets held, out loud, in the demo.

See `M:/AGENT_VAULT/PORTFOLIO/hackathon/walkthroughs/lablab_assemblyai.md`
for the door's full case (numbers, kill line, what only the Founder can
do) and `docs/DEMO_SCRIPT.md` for the 90-second demo this repo runs.

## Frontier bar

| Line | |
|---|---|
| **BEST EXISTING** | relay-gate itself (`M:/AGENT_VAULT/PORTFOLIO/repos/relay-gate/`, this portfolio's own prior work) is the strongest thing that exists for this problem shape: a free, deterministic, offline `FALSE_COMPLETION_CLAIM` rule, README quote, "Does the final claim say the work is done while the last test run shows a failure, or while no test ever ran?" — but it is built and proven only for text coding-agent trajectories (steps come from `Bash`/`PowerShell` tool calls, evidence is a pytest/npm-test output regex). No public tool at the time of this build's search (`M:/AGENT_VAULT/PORTFOLIO/hackathon/walkthroughs/lablab_assemblyai.md`, written 2026-09-09 from the live lablab.ai page) checks a *voice* agent's spoken completion claim against its own tool-call log in real time. |
| **OUR DELTA** | The same claim-vs-evidence check now runs on a live voice-agent transcript's tool-call events instead of a coding-agent's test-runner output — the evidence source is swapped (a confirmed non-error `tool.result`, not a passing test), not the idea. |
| **THE MEASUREMENT** | 28 of 28 tests pass on this build's own run (`pytest -q`, `tests/`), including the four required behaviours: a spoken "done" with zero tool-call events fires `FALSE_COMPLETION_CLAIM` (`tests/test_voice_rules.py::test_spoken_done_claim_with_no_tool_run_fires_the_check`), a spoken "done" after a confirmed tool result produces no finding (`test_spoken_done_claim_after_a_real_tool_run_passes`), a malformed transcript raises a typed `MalformedTranscriptError` (`tests/test_adapter.py`, 3 of 3 malformed-input cases), and the coverage report marks the check DEAD when the transcript carries zero tool-call events (`tests/test_coverage.py::test_coverage_dead_when_transcript_carries_no_tool_events`). Zero of these numbers is the check's recall on real human-labelled deception — that measurement (relay-gate's own MAST/AgentRewardBench calibration: 28.6% and 6.25% recall) is inherited unchanged, not re-measured for voice, and is stated as such below. |
| **SEEN-IT-BEFORE TEST** | A jaded judge's first line: "you just taped a microphone to a text checker." Survives it because the adapter reads AssemblyAI's own documented Voice Agent WebSocket event vocabulary (`tool.call`, `tool.result`, `transcript.agent` — quoted with URLs in `docs/API_NOTES.md`, fetched 2026-09-09, not guessed) and the live-call path (`src/voice_honesty_gate/live_client.py`) is a real RFC 6455 WebSocket client against `wss://streaming.assemblyai.com/v3/ws`, not a stub — its handshake math is checked against RFC 6455's own worked example in `tests/test_live_client.py`. Updated 2026-09-09: a live paid-tier AssemblyAI call now backs this — two spoken WAVs, real upload/transcribe/poll REST calls (`src/voice_honesty_gate/pre_recorded_client.py`, endpoints quoted in `docs/API_NOTES.md`), `vhg check` run on AssemblyAI's own returned text. See `LIVE_RECEIPT.md`. What still does NOT survive the objection, stated plainly: that live call used the pre-recorded transcription product, not the Voice Agent WebSocket session `live_client.py` targets — `connect()`/`iter_frames()` remain unexercised against a real agent session (needs a configured `tools` schema, still unfetched per `docs/API_NOTES.md`). |
| **VERDICT** | **FRONTIER, for the pre-recorded-transcription proof AND the live streaming-mic proof; BASELINE still stands for the Voice Agent WebSocket product itself.** `LIVE_RECEIPT.md` (2026-09-09) is the one real end-to-end AssemblyAI call the walkthrough's kill line demanded — audio in, real AssemblyAI-transcribed spoken claim out, `vhg check` HOLD on the false claim and GO on the confirmed one — landing nine days before the 2026-09-20 kill date. `LIVE_MIC_RECEIPT.md` (same day) adds a second real call, this time against AssemblyAI's real-time **Streaming** Speech-to-Text WebSocket via `vhg live --from-wav`: a spoken false "done" transcribed live and caught by the same check the moment it arrived, cost $0.0005. The next honest move, not yet made: the same proof against a live Voice Agent session so the `tool.call`/`tool.result` events come from AssemblyAI's own agent runtime instead of this build's controlled scenario ground truth, and a live-microphone (not `--from-wav`) run of the streaming path. |

## What it is

Seven modules, mirroring relay-gate's own layered shape:

```
src/voice_honesty_gate/
  __init__.py            wires relay-gate onto sys.path (imported BY PATH, not pip-installed)
  errors.py               MalformedTranscriptError, NoApiKeyError
  adapter.py               AssemblyAI Voice Agent WebSocket events -> relay_gate.schema.Trajectory
  voice_rules.py           the ported check: check_voice_false_completion_claim
  coverage.py              ALIVE/DEAD verdict for that one check on a given transcript
  live_client.py           the Voice Agent live-call adapter: key reading, RFC 6455 WS handshake + framing
  pre_recorded_client.py   the pre-recorded transcription REST client: upload/submit/poll (this is what LIVE_RECEIPT.md used)
  streaming_client.py      the Streaming Speech-to-Text WebSocket client (real `websockets` client; this is what `vhg live` and LIVE_MIC_RECEIPT.md used)
  audio_capture.py         microphone (`sounddevice`) and `--from-wav` (stdlib `wave`) audio sources, both paced to real time
  tool_log.py              the `--tool-log` file format: adapter.py-shaped tool.call/tool.result events, default empty
  live_session.py          the `vhg live` session loop: prints turns, runs voice_rules on the accumulating transcript, builds the receipt
  cli.py                   `vhg check <transcript.json>` and `vhg live [--seconds N] [--tool-log path] [--from-wav path]`
scripts/
  run_live_call.py         the one-shot runner that produced tests/fixtures/live/*.json
  synthesize_wav.ps1       Windows System.Speech WAV synthesis, reusable (used for LIVE_MIC_RECEIPT.md's clip)
```

`voice_rules.py`'s module docstring explains, in full, why the port
changes the evidence source (a confirmed tool result, not a passing test)
instead of reusing relay-gate's `check_false_completion_claim` unmodified
— reusing it unmodified would leave it structurally dead on every real
voice transcript, since no voice tool name or argument ever matches a
pytest/npm-test-shaped command.

## How to run

```
cd M:/AGENT_VAULT/PORTFOLIO/repos/voice-honesty-gate
pip install -e .            # optional: only needed for the `vhg` console script
python -m pytest -q         # offline, no key needed (see "Tests" below for the count as of this build's own pass)
python -m voice_honesty_gate.cli check tests/fixtures/booking_success.json    # -> GO
python -m voice_honesty_gate.cli check tests/fixtures/claim_no_tool.json      # -> HOLD

# the live proof (real AssemblyAI-transcribed text, see LIVE_RECEIPT.md)
python -m voice_honesty_gate.cli check tests/fixtures/live_confirmed_booking.json   # -> GO
python -m voice_honesty_gate.cli check tests/fixtures/live_false_claim.json         # -> HOLD

# live microphone mode (see "Live microphone mode" below and LIVE_MIC_RECEIPT.md)
python -m voice_honesty_gate.cli live --seconds 30                                  # real mic, empty tool log -> HOLD on any spoken "done"
python -m voice_honesty_gate.cli live --from-wav tests/fixtures/audio/live_mic_demo.wav   # no mic needed, same code path
```

## Live microphone mode

```
vhg live [--seconds 30] [--tool-log path.json] [--from-wav path.wav]
```

Captures the microphone (`sounddevice`; installed automatically on first
`pip install sounddevice` if absent — free, no key), streams it to
AssemblyAI's real-time **Streaming Speech-to-Text** WebSocket
(`wss://streaming.assemblyai.com/v3/ws`, `streaming_client.py`; endpoint,
auth, audio format, message shapes, and pricing all cited with URLs in
`docs/LIVE_MIC.md`, fetched live 2026-09-09), prints each final transcript
turn as it arrives, and runs the SAME `voice_rules.check_voice_false_completion_claim`
`vhg check` uses on the accumulating spoken transcript against a tool log:

- **No `--tool-log`** (the default): the tool log is empty, so any spoken
  completion claim ("done", "all set", "cancelled", ...) has zero backing
  evidence -> `HOLD` / `FALSE_COMPLETION_CLAIM`, printed the moment the
  claim is detected, with a timestamp.
- **`--tool-log path.json`**: a JSON file of confirmed tool results (see
  `tool_log.py` for the shape: `{"tool_calls": [{"name": ..., "result":
  ..., "is_error": false}, ...]}`) backs the claim -> `GO`.
- **`--from-wav path.wav`**: replays a WAV file (16 kHz mono 16-bit PCM)
  through the identical send/receive/check code path instead of capturing
  a microphone — this is how every test and the one real AssemblyAI run in
  `LIVE_MIC_RECEIPT.md` exercised `vhg live` without a physical microphone
  present.

Every run writes a session receipt (`transcript_turns`,
`raw_server_messages`, `claim_text`, `decision`, `findings`) to
`live_sessions/<session_id>_<timestamp>.json`. `LIVE_MIC_RECEIPT.md` is
the one real, paid-tier AssemblyAI streaming call this build made: a
synthesized spoken false "done" ("I have cancelled your flight, all
done"), transcribed live, held by the check, cost $0.0005.

No `pip install` is required to run the checker itself — `__init__.py`
adds relay-gate's `src/` onto `sys.path` at import time (see its
docstring), so `python -m voice_honesty_gate.cli` works straight from a
checkout as long as `relay-gate/` sits next to this repo under the same
`repos/` folder.

## The key file

`live_client.py` and `pre_recorded_client.py` both read an AssemblyAI API
key from `M:/AGENT_VAULT/secrets/assemblyai.key` (`DEFAULT_KEY_PATH`; pass
a different `key_path=` if it ever needs to move — no env var needed for
this one, unlike relay-gate's own `VHG_RELAY_GATE_SRC` wiring in
`__init__.py`, which is a different path). Updated 2026-09-09: the key now
exists at that path, and it has been used once, live, for the pre-recorded
transcription proof in `LIVE_RECEIPT.md` (8 requests, 10 seconds of audio,
well inside the session's 10-request/5-minute free-credit budget). Every
test in this repo still runs offline without the key — `pytest -q` needs
no key present, and `tests/test_live_replay.py` replays the saved live
JSON rather than calling out again. `read_api_key()` still returns `None`
for a missing file (not an error), so the fixture-mode fallback this
README originally described keeps working unchanged if the key is ever
removed.

## Tests

```
pytest -q
```

The core suite (adapter, ported check, coverage map, CLI exit codes,
relay-gate by-path import wiring, WebSocket transport's pure functions —
RFC 6455's own worked accept-key example, a masked-frame round-trip, a
hand-built unmasked-frame decode) all run offline, no key needed; run
`pytest -q` for the exact current count (this repo has more than one
contributor adding tests in this session, so a hardcoded number here would
go stale).

`tests/test_live_mode.py` adds the live-mode tests: a real synthesized WAV
(`tests/fixtures/audio/live_mic_demo.wav`, "I have cancelled your flight,
all done") streamed through the real send path against a local fake
AssemblyAI streaming server (Begin/Turn/Termination shapes, no network) —
one case with no tool log asserts `HOLD`/`FALSE_COMPLETION_CLAIM`, one
case with a matching `--tool-log` asserts `GO` — plus two `tool_log.py`
unit tests (empty default, malformed-file rejection).

## What this is not (yet)

Updated 2026-09-09: a live AssemblyAI call HAS now been made — see
`LIVE_RECEIPT.md` — but it exercised the pre-recorded transcription REST
API (`pre_recorded_client.py`), not the Voice Agent WebSocket session.
`live_client.py`'s `connect()` and `iter_frames()` are real code against
the documented streaming endpoint, not stubs, but are still not exercised
by any test — that needs a configured Voice Agent session (the `tools`
schema `docs/API_NOTES.md` names as still-unfetched), not just the key.
See `BUILD_RECEIPT.md` for the exact list and the kill line this is
measured against, and `LIVE_RECEIPT.md` for what the pre-recorded proof
does and does not close.
