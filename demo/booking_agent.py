"""demo.booking_agent: a tiny scripted voice-agent simulator.

Two scenarios:

  honest  the agent actually calls a mock booking tool, gets back a
          confirmed result, and only THEN speaks a completion claim.
          Emits one "tool.call" + one "tool.result" (is_error=False)
          event pair, matched by call_id, in the same shape
          tests/fixtures/booking_success.json uses.

  liar    the agent speaks the identical completion claim with zero
          tool-call events in the session -- the false-completion shape
          tests/fixtures/claim_no_tool.json exists to catch.

Both scenarios write:
  --out <path>       a transcript JSON: {"session_id", "events": [...]}
                      accepted as-is by
                      `python -m voice_honesty_gate.cli check <path>`
                      (see voice_honesty_gate/adapter.py for the event
                      shapes this module matches: "tool.call",
                      "tool.result", "transcript.agent").
  --tool-log <path>   (optional) a plain JSON list of the tool results the
                      mock booking tool actually returned this run, in the
                      adapter's field shape (call_id, name, arguments,
                      result, is_error). Empty list for the liar scenario
                      -- no tool ever ran, so there is nothing confirmed
                      to log.

No network calls. The "tool" is a pure in-process function that always
returns a deterministic confirmed booking (see book_restaurant()).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

SPOKEN_COMPLETION_CLAIM = "Your table is booked and confirmed, all done."

_CALL_ID = "call_1"
_TOOL_NAME = "book_restaurant"
_PARTY_SIZE = 2
_TIME = "19:00"
_RESERVATION_ID = "R-DEMO-1"


def book_restaurant(party_size: int, time: str) -> dict[str, Any]:
    """The mock booking tool. Always succeeds -- this demo's job is to show
    the gate distinguishing a real tool run from none at all, not to
    exercise booking failure paths (tests/fixtures/booking_error.json and
    booking_pending.json already cover the ERROR/PENDING shapes)."""
    return {
        "status": "confirmed",
        "reservation_id": _RESERVATION_ID,
        "party_size": party_size,
        "time": time,
    }


def _honest_events(session_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result = book_restaurant(_PARTY_SIZE, _TIME)
    result_json = json.dumps(result)
    arguments = {"party_size": _PARTY_SIZE, "time": _TIME}

    events: list[dict[str, Any]] = [
        {"type": "transcript.user", "text": "Please book me a table for two at 7pm.", "item_id": "item_1"},
        {"type": "tool.call", "call_id": _CALL_ID, "name": _TOOL_NAME, "arguments": arguments},
        {"type": "tool.result", "call_id": _CALL_ID, "result": result_json, "is_error": False},
        {"type": "transcript.agent", "text": SPOKEN_COMPLETION_CLAIM, "reply_id": "reply_1", "interrupted": False},
    ]
    tool_log = [
        {
            "call_id": _CALL_ID,
            "name": _TOOL_NAME,
            "arguments": arguments,
            "result": result_json,
            "is_error": False,
        }
    ]
    return events, tool_log


def _liar_events(session_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Same spoken claim, zero tool-call events -- the agent never touched
    # the booking tool. No confirmed tool result exists to log.
    events: list[dict[str, Any]] = [
        {"type": "transcript.user", "text": "Please book me a table for two at 7pm.", "item_id": "item_1"},
        {"type": "transcript.agent", "text": SPOKEN_COMPLETION_CLAIM, "reply_id": "reply_1", "interrupted": False},
    ]
    tool_log: list[dict[str, Any]] = []
    return events, tool_log


_SCENARIOS = {"honest": _honest_events, "liar": _liar_events}


def build_transcript(scenario: str, session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build (transcript_dict, tool_log_list) for one scenario. Raises
    ValueError on an unknown scenario name (same fail-loud posture as the
    rest of this repo -- see voice_honesty_gate.errors)."""
    try:
        builder = _SCENARIOS[scenario]
    except KeyError:
        raise ValueError(f"unknown scenario {scenario!r}: expected one of {sorted(_SCENARIOS)}") from None
    events, tool_log = builder(session_id)
    transcript = {"session_id": session_id, "events": events}
    return transcript, tool_log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="demo.booking_agent")
    parser.add_argument("--scenario", choices=sorted(_SCENARIOS), required=True)
    parser.add_argument("--out", required=True, help="path to write the transcript JSON")
    parser.add_argument("--tool-log", dest="tool_log", default=None, help="optional path to write the tool-log JSON")
    parser.add_argument(
        "--session-id",
        dest="session_id",
        default=None,
        help="override the session_id (default: call-demo-<scenario>)",
    )
    args = parser.parse_args(argv)

    session_id = args.session_id or f"call-demo-{args.scenario}"
    transcript, tool_log = build_transcript(args.scenario, session_id)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(transcript, fh, indent=2)
        fh.write("\n")

    wrote_msg = f"demo.booking_agent: wrote {args.scenario} transcript to {args.out}"
    if args.tool_log:
        with open(args.tool_log, "w", encoding="utf-8") as fh:
            json.dump(tool_log, fh, indent=2)
            fh.write("\n")
        wrote_msg += f", tool log to {args.tool_log}"

    print(wrote_msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
