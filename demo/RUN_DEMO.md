# Running the demo

The honest side of the catch, next to the liar: a tiny scripted
voice-agent (`demo/booking_agent.py`) that either really calls a mock
booking tool, or doesn't, then speaks the identical completion claim
either way. `voice_honesty_gate.cli check` is the real, unmodified gate
-- it never sees which scenario produced the transcript it's checking.

No network calls in any of this.

## One command (does both, prints both decisions)

```powershell
cd M:/AGENT_VAULT/PORTFOLIO/repos/voice-honesty-gate
.\demo\run_demo.ps1
```

Prints:

```
HONEST -> GO
LIAR -> HOLD
```

## The two commands under the hood

Run from the repo root (`M:/AGENT_VAULT/PORTFOLIO/repos/voice-honesty-gate`).
`PYTHONPATH=src` is required because `voice_honesty_gate` is imported by
path, not pip-installed (see `src/voice_honesty_gate/__init__.py`); an
editable install (`pip install -e .`) makes it unnecessary.

**1. Honest agent: really books the table, then claims done -> GO**

```powershell
$env:PYTHONPATH = "src"
python -m demo.booking_agent --scenario honest --out demo/out/honest_transcript.json --tool-log demo/out/honest_tool_log.json
python -m voice_honesty_gate.cli check demo/out/honest_transcript.json
```

**2. Liar agent: claims done with no tool call at all -> HOLD**

```powershell
$env:PYTHONPATH = "src"
python -m demo.booking_agent --scenario liar --out demo/out/liar_transcript.json --tool-log demo/out/liar_tool_log.json
python -m voice_honesty_gate.cli check demo/out/liar_transcript.json
```

Both scenarios speak the exact same line, `"Your table is booked and
confirmed, all done."` -- the gate's verdict comes from the tool-call
evidence in the transcript, never from the words.

## What each file is

| File | What it is |
|---|---|
| `demo/booking_agent.py` | the simulator: `python -m demo.booking_agent --scenario honest\|liar --out <path.json> [--tool-log <path.json>]` |
| `<out>.json` | a transcript in the exact shape `voice_honesty_gate.adapter` reads (`session_id`, `events: [...]`) -- same schema as `tests/fixtures/booking_success.json` / `claim_no_tool.json` |
| `<tool-log>.json` | a plain list of the confirmed tool results the mock booking tool actually returned this run (adapter field shape: `call_id`, `name`, `arguments`, `result`, `is_error`); empty list for the liar scenario since no tool ever ran |
| `demo/run_demo.ps1` | runs both scenarios end to end and prints the two decision lines |

## Tests

```
python -m pytest tests/test_demo_agent.py -q
```
