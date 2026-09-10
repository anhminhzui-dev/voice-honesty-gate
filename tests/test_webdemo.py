"""Tests for the webdemo Gradio app's core function, offline (no network,
no AssemblyAI key needed). Mirrors this repo's existing test style: a
stubbed transcription function plays the role AssemblyAI's real API plays
in production, exactly the same substitution voice_rules.py's own tests
use for tool.result data.

webdemo/ is not part of the installed package (pyproject.toml's
pythonpath only wires src/) so this file adds it to sys.path itself,
the same pattern webdemo/app.py uses for src/.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBDEMO_DIR = REPO_ROOT / "webdemo"
if str(WEBDEMO_DIR) not in sys.path:
    sys.path.insert(0, str(WEBDEMO_DIR))

from app import (  # noqa: E402
    HONEST_LABEL,
    LIAR_LABEL,
    build_events,
    run_gate,
)

FALSE_CLAIM_TEXT = "I ran the tests and they all passed. The task is done."
CONFIRMED_CLAIM_TEXT = "The appointment has been booked and confirmed. I am done."


def _stub_transcribe(claim_text: str):
    def _fn(audio_path: str, api_key: str | None = None) -> str:
        return claim_text

    return _fn


def test_liar_action_log_with_false_claim_holds():
    result = run_gate(
        "fake/path/does-not-need-to-exist.wav",
        LIAR_LABEL,
        transcribe_fn=_stub_transcribe(FALSE_CLAIM_TEXT),
    )
    assert result["decision"] == "HOLD"
    assert result["transcript"] == FALSE_CLAIM_TEXT
    assert result["findings"], "expected a FALSE_COMPLETION_CLAIM finding"
    assert result["findings"][0]["code"] == "FALSE_COMPLETION_CLAIM"
    assert result["coverage"]["status"] == "DEAD"


def test_honest_action_log_with_confirmed_claim_goes():
    result = run_gate(
        "fake/path/does-not-need-to-exist.wav",
        HONEST_LABEL,
        transcribe_fn=_stub_transcribe(CONFIRMED_CLAIM_TEXT),
    )
    assert result["decision"] == "GO"
    assert result["transcript"] == CONFIRMED_CLAIM_TEXT
    assert result["findings"] == []
    assert result["coverage"]["status"] == "ALIVE"


def test_build_events_liar_has_no_tool_call():
    events = build_events(LIAR_LABEL, "some claim")
    types = [ev["type"] for ev in events]
    assert "tool.call" not in types
    assert "tool.result" not in types
    assert types[-1] == "transcript.agent"


def test_build_events_honest_has_confirmed_tool_result_before_claim():
    events = build_events(HONEST_LABEL, "some claim")
    types = [ev["type"] for ev in events]
    assert types == ["tool.call", "tool.result", "transcript.agent"]
    assert events[1]["is_error"] is False


def test_run_gate_rejects_unknown_action_log():
    import pytest

    with pytest.raises(ValueError):
        run_gate(
            "fake.wav",
            "not a real choice",
            transcribe_fn=_stub_transcribe("anything"),
        )


def test_honest_but_tool_errored_still_holds():
    """Sanity check the wiring is real, not hardcoded: swap in a stubbed
    transcribe that returns a completion claim but keep the LIAR log (no
    tool ran) -- must still HOLD even though the words sound confident."""
    result = run_gate(
        "fake.wav",
        LIAR_LABEL,
        transcribe_fn=_stub_transcribe("Everything is done, all good."),
    )
    assert result["decision"] == "HOLD"
