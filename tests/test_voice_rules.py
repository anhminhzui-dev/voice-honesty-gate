import os

import voice_honesty_gate  # noqa: F401
from relay_gate.reasons import ReasonCode
from voice_honesty_gate.adapter import load_transcript
from voice_honesty_gate.voice_rules import check_voice_false_completion_claim

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name: str) -> str:
    return os.path.join(FIXTURES, name)


def test_spoken_done_claim_with_no_tool_run_fires_the_check():
    """The central proof case for the whole entry: the agent says 'done'
    and never called a tool at all."""
    t = load_transcript(_fixture("claim_no_tool.json"))
    findings = check_voice_false_completion_claim(t)
    assert len(findings) == 1
    assert findings[0].reason == ReasonCode.FALSE_COMPLETION_CLAIM
    assert findings[0].category == "hold"
    assert "no tool was ever called" in findings[0].detail


def test_spoken_done_claim_after_a_real_tool_run_passes():
    t = load_transcript(_fixture("booking_success.json"))
    findings = check_voice_false_completion_claim(t)
    assert findings == []


def test_spoken_done_claim_after_a_tool_error_holds():
    t = load_transcript(_fixture("booking_error.json"))
    findings = check_voice_false_completion_claim(t)
    assert len(findings) == 1
    assert findings[0].reason == ReasonCode.FALSE_COMPLETION_CLAIM
    assert findings[0].category == "hold"
    assert "errored" in findings[0].detail


def test_spoken_done_claim_with_unconfirmed_tool_result_is_ambiguous():
    t = load_transcript(_fixture("booking_pending.json"))
    findings = check_voice_false_completion_claim(t)
    assert len(findings) == 1
    assert findings[0].reason == ReasonCode.AMBIGUOUS_COMPLETION_EVIDENCE
    assert findings[0].category == "ambiguous"


def test_non_completion_claim_produces_no_finding():
    t = load_transcript(_fixture("no_claim_smalltalk.json"))
    findings = check_voice_false_completion_claim(t)
    assert findings == []
