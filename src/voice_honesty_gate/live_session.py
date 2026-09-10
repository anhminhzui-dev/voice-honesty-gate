"""The `live` mode session loop: streams audio to AssemblyAI's Streaming
Speech-to-Text WebSocket (`streaming_client.py`), prints each final
transcript turn as it arrives, runs the existing (unforked)
`voice_rules.check_voice_false_completion_claim` on the accumulating
transcript against a tool log (`tool_log.py`) the moment a completion
claim appears, and returns the session receipt `cli.py` writes to
`live_sessions/`.

This module owns none of the honesty-check logic itself -- it only builds
a `relay_gate.schema.Trajectory` out of (tool-log events + the
accumulating spoken transcript) via `adapter.events_to_trajectory`, the
exact same adapter fixture-mode `vhg check` already uses, and calls
`check_voice_false_completion_claim` on it, the exact same check.
"""

from __future__ import annotations

import datetime as _dt
import time
from pathlib import Path
from typing import Any, Callable, Iterator

from relay_gate.rules import _COMPLETION_MARKERS  # noqa: E402 (privately reused, see voice_rules.py's own precedent)

from voice_honesty_gate.adapter import events_to_trajectory
from voice_honesty_gate.coverage import voice_coverage
from voice_honesty_gate.streaming_client import stream_transcribe
from voice_honesty_gate.voice_rules import check_voice_false_completion_claim


def _decide(findings) -> str:
    """Same three-way mapping cli.py's `_run_check` uses, kept in one place
    so `live` mode and `check` mode can never silently drift apart."""
    hold = [f for f in findings if f.category == "hold"]
    ambiguous = [f for f in findings if f.category == "ambiguous"]
    if hold:
        return "HOLD"
    if ambiguous:
        return "AMBIGUOUS-HOLD"
    return "GO"


def run_live_session(
    audio_chunks: Iterator[bytes],
    sample_rate: int,
    *,
    tool_log_events: list[dict[str, Any]] | None = None,
    session_id: str = "live-session",
    api_key: str | None = None,
    key_path: Path | str | None = None,
    ws_url: str | None = None,
    print_fn: Callable[[str], None] = print,
    now_fn: Callable[[], _dt.datetime] = _dt.datetime.now,
) -> dict[str, Any]:
    """Run one live streaming session end to end and return the receipt
    dict `cli.py` writes to `live_sessions/<session_id>_<timestamp>.json`.

    `ws_url` lets tests point this at a local fake streaming server instead
    of AssemblyAI's real endpoint -- `streaming_client.stream_transcribe`
    forwards it unchanged to `websockets.sync.client.connect`.
    """
    tool_log_events = tool_log_events or []
    transcript_turns: list[dict[str, Any]] = []
    raw_server_messages: list[dict[str, Any]] = []
    accumulated_lines: list[str] = []
    claim_detected_at: str | None = None
    last_decision: str | None = None
    last_findings: list[dict[str, Any]] = []
    last_coverage: dict[str, Any] | None = None

    kwargs: dict[str, Any] = {"sample_rate": sample_rate, "on_raw_event": raw_server_messages.append}
    if api_key is not None:
        kwargs["api_key"] = api_key
    if key_path is not None:
        kwargs["key_path"] = key_path
    if ws_url is not None:
        kwargs["ws_url"] = ws_url

    for turn in stream_transcribe(audio_chunks, **kwargs):
        if not turn.end_of_turn:
            continue  # partials are not printed or checked, only finals (goal's stated behaviour)

        stamp = now_fn().strftime("%H:%M:%S")
        print_fn(f"[{stamp}] turn {turn.turn_order}: {turn.transcript}")
        transcript_turns.append({"timestamp": stamp, "turn_order": turn.turn_order, "text": turn.transcript})
        if turn.transcript.strip():
            accumulated_lines.append(turn.transcript.strip())

        accumulated_claim = " ".join(accumulated_lines)
        events = list(tool_log_events) + [{"type": "transcript.agent", "text": accumulated_claim}]
        trajectory = events_to_trajectory(session_id, events)
        findings = check_voice_false_completion_claim(trajectory)
        coverage = voice_coverage(trajectory)
        decision = _decide(findings)

        last_decision = decision
        last_findings = [{"code": f.reason.value, "category": f.category, "detail": f.detail} for f in findings]
        last_coverage = {
            "check": coverage.check,
            "status": coverage.status,
            "field": coverage.field,
            "detail": coverage.detail,
        }

        marker_present = any(m in accumulated_claim.lower() for m in _COMPLETION_MARKERS)
        if marker_present and claim_detected_at is None:
            claim_detected_at = stamp
            print_fn(f"[{stamp}] completion claim detected -> decision: {decision}")
            if findings:
                for f in findings:
                    print_fn(f"[{stamp}]   {f.reason.value}: {f.detail}")

    if claim_detected_at is None:
        stamp = now_fn().strftime("%H:%M:%S")
        print_fn(f"[{stamp}] session ended, no spoken completion claim detected")

    return {
        "session_id": session_id,
        "sample_rate": sample_rate,
        "transcript_turns": transcript_turns,
        "raw_server_messages": raw_server_messages,
        "claim_text": " ".join(accumulated_lines),
        "claim_detected_at": claim_detected_at,
        "decision": last_decision or "NO_CLAIM",
        "findings": last_findings,
        "coverage": last_coverage,
        "tool_log_call_count": len(tool_log_events) // 2,  # each tool call contributes one tool.call + one tool.result event
    }
