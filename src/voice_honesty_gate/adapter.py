"""Transcript adapter: AssemblyAI Voice Agent WebSocket events -> relay_gate.schema.Trajectory.

A saved transcript is a JSON file:

    {
      "session_id": "call-001",
      "allowed_tools": ["book_restaurant"],   // optional
      "events": [ {"type": "...", ...}, ... ]
    }

where each event in "events" is one AssemblyAI Voice Agent API WebSocket
event, in the exact shapes quoted in docs/API_NOTES.md (fetched from
assemblyai.com/docs, 2026-09-09). Only three event types are read; every
other documented event (session.ready, input.speech.started,
transcript.user, transcript.*.delta, reply.started, session.error, ...) is
ignored -- it carries nothing relay_gate's ported check needs:

  "tool.call"      {"type": "tool.call", "call_id": "...", "name": "...", "arguments": {...}}
                    -> becomes one relay_gate.schema.Step. Missing "call_id"
                    or "name" is a malformed transcript, not a silent skip:
                    a tool the adapter cannot place in the trajectory is
                    exactly the kind of gap the honesty check depends on
                    not having.

  "tool.result"     {"type": "tool.result", "call_id": "...", "result": "...", "is_error": bool}
                    -> matched to its "tool.call" by call_id and becomes
                    that Step's `output`. A call_id with no matching
                    tool.call is ignored (nothing to attach it to); a
                    tool.call with no matching tool.result becomes a Step
                    whose output starts with "PENDING:" (see below).

  "transcript.agent" {"type": "transcript.agent", "text": "...", ...}
                    -> the LAST such event's "text" becomes
                    Trajectory.final_claim, mirroring relay_gate's own
                    schema (one final claim per trajectory). Earlier
                    transcript.agent events (mid-call remarks) are not the
                    claim being checked.

Step.output is prefixed to carry outcome, not just payload, because
voice_rules.check_voice_false_completion_claim reads only the LAST step's
output text to decide HOLD / GO / AMBIGUOUS, the same one-field contract
relay_gate.rules.check_false_completion_claim uses on its own last-test-
run output:

  "ERROR: <result>"    tool.result arrived with is_error true
  "PENDING: <detail>"  no tool.result event ever arrived for this call_id
  "<result>"           tool.result arrived with is_error false
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from relay_gate.schema import Trajectory  # noqa: E402  (import-by-path wired in __init__.py)

from voice_honesty_gate.errors import MalformedTranscriptError


def events_to_trajectory(
    session_id: str,
    events: list[dict[str, Any]],
    allowed_tools: tuple[str, ...] | list[str] = (),
) -> Trajectory:
    tool_calls: dict[str, dict[str, Any]] = {}
    tool_results: dict[str, dict[str, Any]] = {}
    call_order: list[str] = []
    agent_texts: list[str] = []

    for i, ev in enumerate(events):
        if not isinstance(ev, dict) or "type" not in ev:
            raise MalformedTranscriptError(
                f"event {i} in session {session_id!r} is not a JSON object carrying a \"type\" field: {ev!r}"
            )
        etype = ev["type"]

        if etype == "tool.call":
            call_id = ev.get("call_id")
            name = ev.get("name")
            if not call_id or not name:
                raise MalformedTranscriptError(
                    f"event {i} in session {session_id!r} is a \"tool.call\" event missing a required field: "
                    f"expected non-empty \"call_id\" and \"name\" (AssemblyAI Voice Agent API shape, see "
                    f"docs/API_NOTES.md); found {ev!r}"
                )
            tool_calls[call_id] = {"name": name, "arguments": dict(ev.get("arguments", {}) or {})}
            if call_id not in call_order:
                call_order.append(call_id)

        elif etype == "tool.result":
            call_id = ev.get("call_id")
            if not call_id:
                raise MalformedTranscriptError(
                    f"event {i} in session {session_id!r} is a \"tool.result\" event missing required field "
                    f"\"call_id\" (AssemblyAI Voice Agent API shape, see docs/API_NOTES.md); found {ev!r}"
                )
            tool_results[call_id] = {
                "result": ev.get("result", ""),
                "is_error": bool(ev.get("is_error", False)),
            }

        elif etype == "transcript.agent":
            agent_texts.append(str(ev.get("text", "")))

        # every other documented event type is read-and-ignored on purpose (see module docstring)

    steps: list[dict[str, Any]] = []
    for call_id in call_order:
        call = tool_calls[call_id]
        result = tool_results.get(call_id)
        if result is None:
            output = f"PENDING: no tool.result event ever arrived for call_id {call_id!r}"
        elif result["is_error"]:
            output = f"ERROR: {result['result']}"
        else:
            output = str(result["result"])
        steps.append({"tool": call["name"], "args": call["arguments"], "output": output})

    final_claim = agent_texts[-1] if agent_texts else ""

    return Trajectory.from_dict(
        {
            "trajectory_id": session_id,
            "allowed_tools": list(allowed_tools),
            "steps": steps,
            "final_claim": final_claim,
        }
    )


def load_transcript(path: str) -> Trajectory:
    """Load a saved AssemblyAI Voice Agent transcript file and adapt it to
    a relay_gate.schema.Trajectory. Raises MalformedTranscriptError (never
    a raw json.JSONDecodeError/KeyError) on anything that does not match
    the shape this module's docstring documents.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise MalformedTranscriptError(f"{path!r} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise MalformedTranscriptError(f"could not read {path!r}: {exc}") from exc

    if not isinstance(raw, dict):
        raise MalformedTranscriptError(
            f"{path!r} does not look like a voice_honesty_gate transcript: expected a top-level JSON "
            f"object with an \"events\" list; found a top-level JSON {type(raw).__name__}"
        )
    if "events" not in raw or not isinstance(raw["events"], list):
        raise MalformedTranscriptError(
            f"{path!r} does not look like a voice_honesty_gate transcript: expected a top-level object "
            f"with an \"events\" list (an AssemblyAI Voice Agent WebSocket event log, see "
            f"docs/API_NOTES.md); found top-level keys {sorted(raw)!r}"
        )

    session_id = raw.get("session_id") or raw.get("trajectory_id") or pathlib.Path(path).stem
    allowed_tools = raw.get("allowed_tools", ())
    return events_to_trajectory(session_id, raw["events"], allowed_tools=allowed_tools)
