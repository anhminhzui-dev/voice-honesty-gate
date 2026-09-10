"""The `--tool-log` file format for `cli.py live` mode.

A tool log is this build's own stand-in for the `tool.call`/`tool.result`
events a real AssemblyAI Voice Agent session would carry (see
`adapter.py`'s module docstring for that event shape) -- in `live` mode
the tool-call evidence comes from here, not from the Streaming
Speech-to-Text socket (`streaming_client.py`), which only ever carries
transcript text (see docs/LIVE_MIC.md's closing section on the product
split). Shape:

    {
      "tool_calls": [
        {"name": "cancel_flight", "result": "{\"status\": \"cancelled\"}", "is_error": false},
        ...
      ]
    }

`call_id` and `arguments` are optional (filled in with a deterministic
placeholder if omitted) since a demo operator writing this file by hand
only cares about "what tool ran and did it succeed", not wiring call ids
by hand. The default (no `--tool-log` given, or an empty file) is zero
tool calls, so `check_voice_false_completion_claim` sees a spoken
completion claim with no backing evidence at all and fires
`FALSE_COMPLETION_CLAIM` -- exactly the goal's stated default behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from voice_honesty_gate.errors import MalformedTranscriptError


def load_tool_log_events(path: Path | str | None) -> list[dict[str, Any]]:
    """Return a list of adapter.py-shaped `tool.call`/`tool.result` events
    built from a tool-log JSON file, or `[]` if `path` is None (the
    documented default: an empty tool log, so any spoken completion claim
    is unbacked)."""
    if path is None:
        return []

    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MalformedTranscriptError(f"{path!s} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise MalformedTranscriptError(f"could not read tool log {path!s}: {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("tool_calls"), list):
        raise MalformedTranscriptError(
            f"{path!s} does not look like a voice_honesty_gate tool log: expected a top-level object "
            f"with a \"tool_calls\" list; found {raw!r}"
        )

    events: list[dict[str, Any]] = []
    for i, entry in enumerate(raw["tool_calls"]):
        if not isinstance(entry, dict) or not entry.get("name"):
            raise MalformedTranscriptError(
                f"tool_calls[{i}] in {path!s} is missing required field \"name\": found {entry!r}"
            )
        call_id = entry.get("call_id") or f"tool_log_call_{i}"
        events.append(
            {
                "type": "tool.call",
                "call_id": call_id,
                "name": entry["name"],
                "arguments": entry.get("arguments", {}),
            }
        )
        events.append(
            {
                "type": "tool.result",
                "call_id": call_id,
                "result": entry.get("result", ""),
                "is_error": bool(entry.get("is_error", False)),
            }
        )
    return events
