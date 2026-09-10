import os

import voice_honesty_gate  # noqa: F401
from voice_honesty_gate.adapter import load_transcript
from voice_honesty_gate.coverage import voice_coverage

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name: str) -> str:
    return os.path.join(FIXTURES, name)


def test_coverage_dead_when_transcript_carries_no_tool_events():
    t = load_transcript(_fixture("claim_no_tool.json"))
    cov = voice_coverage(t)
    assert cov.status == "DEAD"
    assert "no tool-call events" in cov.detail


def test_coverage_alive_when_claim_and_tool_events_present():
    t = load_transcript(_fixture("booking_success.json"))
    cov = voice_coverage(t)
    assert cov.status == "ALIVE"
    assert "1 tool-call step" in cov.detail


def test_coverage_dead_when_final_claim_is_empty():
    # every fixture file has a non-empty claim; build an empty-claim trajectory directly
    from voice_honesty_gate.adapter import events_to_trajectory

    empty_claim_t = events_to_trajectory(
        "no-claim-but-tool-ran",
        [{"type": "tool.call", "call_id": "c1", "name": "noop", "arguments": {}}],
    )
    cov = voice_coverage(empty_claim_t)
    assert cov.status == "DEAD"
    assert "final_claim is empty" in cov.detail
