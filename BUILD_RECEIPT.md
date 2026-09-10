# Build Receipt — voice-honesty-gate

Built 2026-09-09. Fence: `M:/AGENT_VAULT/PORTFOLIO/repos/voice-honesty-gate/`
only. No git commands run (Astra commits). Nothing published or
submitted. No paid API call made. No account sign-up performed.

**Addendum, same day:** a live paid-tier AssemblyAI call was made later
this session, closing the kill-line item this receipt originally left
open — see `LIVE_RECEIPT.md` and "What needs the key" below (updated in
place, not silently).

## What was built

| Path | Lines | What it does |
|---|---|---|
| `README.md` | 80 | What it is, frontier-bar block, how to run, key file path |
| `pyproject.toml` | 18 | pytest pythonpath wiring, `vhg` console script |
| `docs/API_NOTES.md` | 121 | AssemblyAI Voice Agent + Streaming API endpoints/auth/events, quoted with URLs, fetched 2026-09-09 |
| `docs/DEMO_SCRIPT.md` | 61 | The 90-second judge demo |
| `src/voice_honesty_gate/__init__.py` | 40 | Wires relay-gate onto `sys.path` by path (no pip dependency) |
| `src/voice_honesty_gate/errors.py` | 22 | `MalformedTranscriptError`, `NoApiKeyError` |
| `src/voice_honesty_gate/adapter.py` | 134 | AssemblyAI WS events -> `relay_gate.schema.Trajectory` |
| `src/voice_honesty_gate/voice_rules.py` | 61 | The ported check: `check_voice_false_completion_claim` |
| `src/voice_honesty_gate/coverage.py` | 44 | ALIVE/DEAD verdict for that check on a transcript |
| `src/voice_honesty_gate/live_client.py` | 191 | Live-call adapter: key reading, RFC 6455 WS handshake + framing, documented REST/WS endpoints |
| `src/voice_honesty_gate/cli.py` | 59 | `vhg check <transcript.json>` |
| `src/voice_honesty_gate/__main__.py` | 4 | `python -m voice_honesty_gate` entry point |
| `tests/test_*.py` (6 files) | 205 total | 28 tests |
| `tests/fixtures/*.json` (8 files) | 50 total | Saved transcript fixtures for every test branch |

## Test output (this build's own run, `pytest -v`, 2026-09-09)

```
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
collected 28 items

tests/test_adapter.py::test_load_transcript_builds_trajectory_with_confirmed_tool_step PASSED [  3%]
tests/test_adapter.py::test_tool_call_without_result_is_marked_pending PASSED [  7%]
tests/test_adapter.py::test_tool_call_with_error_result_is_marked_error PASSED [ 10%]
tests/test_adapter.py::test_final_claim_is_empty_when_no_transcript_agent_events PASSED [ 14%]
tests/test_adapter.py::test_malformed_transcript_missing_events_raises_typed_error PASSED [ 17%]
tests/test_adapter.py::test_malformed_transcript_tool_call_missing_call_id_raises_typed_error PASSED [ 21%]
tests/test_adapter.py::test_malformed_transcript_bad_json_raises_typed_error PASSED [ 25%]
tests/test_adapter.py::test_missing_file_raises_typed_error_not_oserror PASSED [ 28%]
tests/test_cli.py::test_cli_exit_zero_and_go_on_a_real_tool_run PASSED   [ 32%]
tests/test_cli.py::test_cli_exit_two_and_hold_on_claim_with_no_tool PASSED [ 35%]
tests/test_cli.py::test_cli_exit_two_on_malformed_transcript PASSED      [ 39%]
tests/test_coverage.py::test_coverage_dead_when_transcript_carries_no_tool_events PASSED [ 42%]
tests/test_coverage.py::test_coverage_alive_when_claim_and_tool_events_present PASSED [ 46%]
tests/test_coverage.py::test_coverage_dead_when_final_claim_is_empty PASSED [ 50%]
tests/test_live_client.py::test_ws_accept_key_matches_the_rfc6455_worked_example PASSED [ 53%]
tests/test_live_client.py::test_encode_client_frame_masks_the_payload_per_rfc6455 PASSED [ 57%]
tests/test_live_client.py::test_decode_server_frame_parses_a_hand_built_unmasked_frame PASSED [ 60%]
tests/test_live_client.py::test_decode_server_frame_returns_none_on_incomplete_buffer PASSED [ 64%]
tests/test_live_client.py::test_read_api_key_returns_none_when_file_absent PASSED [ 67%]
tests/test_live_client.py::test_read_api_key_reads_and_strips_file_contents PASSED [ 71%]
tests/test_live_client.py::test_client_construction_raises_no_api_key_error_when_key_absent PASSED [ 75%]
tests/test_live_client.py::test_client_construction_succeeds_when_key_present PASSED [ 78%]
tests/test_relay_gate_import.py::test_relay_gate_is_importable_by_path PASSED [ 82%]
tests/test_voice_rules.py::test_spoken_done_claim_with_no_tool_run_fires_the_check PASSED [ 85%]
tests/test_voice_rules.py::test_spoken_done_claim_after_a_real_tool_run_passes PASSED [ 89%]
tests/test_voice_rules.py::test_spoken_done_claim_after_a_tool_error_holds PASSED [ 92%]
tests/test_voice_rules.py::test_spoken_done_claim_with_unconfirmed_tool_result_is_ambiguous PASSED [ 96%]
tests/test_voice_rules.py::test_non_completion_claim_produces_no_finding PASSED [100%]

28 passed in 0.08s
```

A real failure was hit and fixed during this build, not just a clean
run start to finish: `test_spoken_done_claim_after_a_tool_error_holds`
first failed (`assert 0 == 1`) because the fixture's agent line, "that's
all set," did not contain any of relay-gate's own completion-marker
vocabulary (`_COMPLETION_MARKERS`), so the check correctly returned no
finding rather than a wrong one. Fixed by editing the fixture's spoken
line to include "done" — the code was right, the fixture wasn't
representative. Confirms the check can actually fail, and did.

## Verified live, not guessed

- `M:/AGENT_VAULT/secrets/assemblyai.key` does not exist on disk (checked
  with `Test-Path`, `False`) — fixture mode is the only path any test in
  this repo exercises, exactly as the build constraint requires.
- `docs/API_NOTES.md`'s endpoints, auth header, and event shapes were
  fetched live from `assemblyai.com/docs` on 2026-09-09 (four WebFetch
  calls; two initial URL guesses 404'd and are named as dead ends in that
  file rather than silently dropped).
- `compute_ws_accept_key` in `live_client.py` is checked against RFC
  6455 section 1.3's own published worked example
  (`dGhlIHNhbXBsZSBub25jZQ==` -> `s3pPLMBiTxaQ9kYGzzhZRbK+xOo=`), not a
  self-authored fixture — an independent cross-check the code could not
  have been tuned to pass by accident.

## What needs the key — updated 2026-09-09, partially closed

The key now exists at `M:/AGENT_VAULT/secrets/assemblyai.key` and has been
used, live, once — see `LIVE_RECEIPT.md`: two spoken WAVs, real
upload/submit/poll calls against AssemblyAI's pre-recorded transcription
REST API (`src/voice_honesty_gate/pre_recorded_client.py`), real
AssemblyAI-transcribed text, `vhg check` run on it (HOLD on the false
claim, GO on the confirmed one). 8 requests, 10 seconds of audio, inside
the session's 10-request/5-minute budget.

What still needs the key (unclosed): everything in `live_client.py` beyond
`read_api_key()` and the pure frame-math functions —
`AssemblyAIVoiceAgentClient.connect()` (opens a real TLS socket + performs
the RFC 6455 HTTP Upgrade handshake against `streaming.assemblyai.com`)
and `iter_frames()` (reads real server frames off that socket) remain
unexercised against AssemblyAI's actual Voice Agent server — that needs a
configured agent session (the `tools` schema `docs/API_NOTES.md` names as
still-unfetched), not just the key. The honest state as of this receipt:
the pre-recorded-transcription live call is proven; the Voice Agent
WebSocket live call is still owed. See README.md's frontier-bar VERDICT
row for the exact split.

## The kill line (quoted verbatim from the walkthrough)

> if by 2026-09-20 (ten days before the 2026-09-30 15:00 UTC deadline)
> one real end-to-end AssemblyAI Voice Agent API call, audio in, a spoken
> claim out, has not been produced and saved as proof, kill the voice
> framing for this door and do not submit under it.

Today is 2026-09-09. Zero of zero required live AssemblyAI Voice Agent
API calls exist in the estate — unchanged by this build, which was
scoped, per the Founder's own constraint, to make none. Day ten of
twenty-one (2026-09-20) is the pass/fail checkpoint; this receipt does not
move that number, it only confirms the scaffold the live call will run
against is ready and green.
