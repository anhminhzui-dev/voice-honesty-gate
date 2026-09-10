"""Typed errors.

Mirrors relay_gate.coverage.TraceFormatError's contract: a caller should
never have to parse free text to know what went wrong. Every error names
the path, what was expected, and what was found.
"""

from __future__ import annotations


class MalformedTranscriptError(ValueError):
    """Raised when a saved transcript file does not carry the shape
    voice_honesty_gate needs to build a relay_gate.schema.Trajectory: a
    top-level JSON object with an "events" list, where every "tool.call"
    event carries "call_id" and "name" (AssemblyAI Voice Agent WebSocket
    event fields, see docs/API_NOTES.md), and every "tool.result" event
    carries "call_id". Also raised when the file is not valid JSON, or is
    not a JSON object at all.
    """


class NoApiKeyError(RuntimeError):
    """Raised by live_client when no AssemblyAI API key is on disk at the
    configured key path. This is the expected, designed-for state for this
    build (no paid API call, no account sign-up) -- callers should catch
    this and fall back to fixture mode against a saved transcript, not
    treat it as an unexpected failure.
    """
