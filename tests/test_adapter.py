import os

import pytest

import voice_honesty_gate  # noqa: F401
from voice_honesty_gate.adapter import events_to_trajectory, load_transcript
from voice_honesty_gate.errors import MalformedTranscriptError

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name: str) -> str:
    return os.path.join(FIXTURES, name)


def test_load_transcript_builds_trajectory_with_confirmed_tool_step():
    t = load_transcript(_fixture("booking_success.json"))
    assert t.trajectory_id == "call-001-booking-success"
    assert len(t.steps) == 1
    step = t.steps[0]
    assert step.tool == "book_restaurant"
    assert step.args == {"party_size": 2, "time": "19:00"}
    assert "confirmed" in step.output
    assert not step.output.startswith(("ERROR:", "PENDING:"))
    assert "booked your table" in t.final_claim


def test_tool_call_without_result_is_marked_pending():
    t = load_transcript(_fixture("booking_pending.json"))
    assert len(t.steps) == 1
    assert t.steps[0].output.startswith("PENDING:")


def test_tool_call_with_error_result_is_marked_error():
    t = load_transcript(_fixture("booking_error.json"))
    assert len(t.steps) == 1
    assert t.steps[0].output.startswith("ERROR:")
    assert "fully booked" in t.steps[0].output


def test_final_claim_is_empty_when_no_transcript_agent_events():
    events = [{"type": "transcript.user", "text": "hello", "item_id": "i1"}]
    t = events_to_trajectory("no-agent-text", events)
    assert t.final_claim == ""
    assert t.steps == ()


def test_malformed_transcript_missing_events_raises_typed_error():
    with pytest.raises(MalformedTranscriptError, match="events"):
        load_transcript(_fixture("malformed_missing_events.json"))


def test_malformed_transcript_tool_call_missing_call_id_raises_typed_error():
    with pytest.raises(MalformedTranscriptError, match="tool.call"):
        load_transcript(_fixture("malformed_tool_call_no_call_id.json"))


def test_malformed_transcript_bad_json_raises_typed_error():
    with pytest.raises(MalformedTranscriptError, match="not valid JSON"):
        load_transcript(_fixture("malformed_not_json.json"))


def test_missing_file_raises_typed_error_not_oserror():
    with pytest.raises(MalformedTranscriptError):
        load_transcript(_fixture("does_not_exist.json"))
