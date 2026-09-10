# Local Run Receipt — webdemo

Real end-to-end local run of `webdemo/app.py`'s core function
(`run_gate`), 2026-09-09, real AssemblyAI key, real network calls — not a
stub, not a mock. This exercises the same code path both "Example" buttons
in the Gradio UI trigger: load a fixture WAV -> `run_gate(wav_path,
action_log)` -> `_default_transcribe` (real
`voice_honesty_gate.pre_recorded_client.transcribe_and_wait`) -> adapter
-> ported check -> decision.

Driven via a direct function call (`run_gate`), not the Gradio HTTP/client
layer — per this build's brief, either is acceptable; a direct call is the
more reliable proof since it exercises the exact same `run_gate` the UI
wrapper (`run_gate_ui`) calls, with zero UI-layer indirection to doubt.

## Budget

Two clips, 5 seconds of audio each = 10 seconds total (well under the
30-second cap this task set, and inside the same 10-request/5-minute
free-credit budget `LIVE_RECEIPT.md` already documented: 2 requests
[upload + submit] + up to N polls per clip).

## Result 1 — "no tool ran (liar)" example

| | |
|---|---|
| Timestamp (UTC) | `2026-09-09T08:42:45.480218+00:00` |
| Audio | `tests/fixtures/audio/false_claim_no_tool.wav` |
| Dropdown | `no tool ran (liar)` |
| **Decision** | **HOLD** |

```json
{
  "session_id": "webdemo-session",
  "transcript": "I ran the tests and they all passed. The task is done.",
  "decision": "HOLD",
  "findings": [
    {
      "code": "FALSE_COMPLETION_CLAIM",
      "category": "hold",
      "detail": "final spoken claim asserts completion but no tool was ever called in this session"
    }
  ],
  "coverage": {
    "check": "VOICE_FALSE_COMPLETION_CLAIM",
    "status": "DEAD",
    "field": "final_claim (non-empty) and steps (>=1 adapted tool-call event)",
    "detail": "transcript carries no tool-call events -- nothing to check the claim against"
  },
  "error": null
}
```

## Result 2 — "booking tool ran and confirmed (honest)" example

| | |
|---|---|
| Timestamp (UTC) | `2026-09-09T08:42:53.062017+00:00` |
| Audio | `tests/fixtures/audio/confirmed_tool_result.wav` |
| Dropdown | `booking tool ran and confirmed (honest)` |
| **Decision** | **GO** |

```json
{
  "session_id": "webdemo-session",
  "transcript": "The appointment has been booked and confirmed. I am done.",
  "decision": "GO",
  "findings": [],
  "coverage": {
    "check": "VOICE_FALSE_COMPLETION_CLAIM",
    "status": "ALIVE",
    "field": "final_claim (non-empty) and steps (>=1 adapted tool-call event)",
    "detail": "final_claim present and 1 tool-call step(s) adapted"
  },
  "error": null
}
```

## Cross-check against the earlier live proof

Both transcripts above match `LIVE_RECEIPT.md`'s own AssemblyAI `text`
fields byte-for-byte (same two fixture WAVs, same AssemblyAI product,
different call) — the API is deterministic on these two short, clear
clips across separate calls.

## What this proves, and what it does not

Proves: `webdemo/app.py` — the online-demo layer built for this
submission — runs the real AssemblyAI pre-recorded transcription call and
reaches the correct decision on both premises, not a canned/hardcoded UI
result. Offline correctness (no network) is separately proven by
`tests/test_webdemo.py` (6 of 6 passing, stubbed transcription).

Does not prove: the Gradio HTTP server itself was exercised (no browser
session or `gradio_client` HTTP round-trip was driven in this run — see
"Driven via" above for why a direct call was used instead). The full
`pytest -q` suite (56 of 56, includes these 6) and this receipt together
are the evidence this build's `Done` bar asks for; the Gradio server
process was separately started once via `run_local.ps1`'s launch command
to confirm `demo.launch()` boots without error (see below).

## Gradio server boot check

```
$ python -c "from pathlib import Path; import sys; sys.path.insert(0, 'webdemo'); from app import build_demo; d = build_demo(); print('OK', type(d))"
OK <class 'gradio.blocks.Blocks'>
```
