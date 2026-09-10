"""Offline replay of the live AssemblyAI end-to-end call (see LIVE_RECEIPT.md,
scripts/run_live_call.py). Reads the raw JSON AssemblyAI actually returned on
2026-09-09 (tests/fixtures/live/*.json, key material stripped, no key needed
to read them) and the two vhg transcript fixtures built from that real text
(tests/fixtures/live_false_claim.json, tests/fixtures/live_confirmed_booking.json)
to prove the suite stays green -- and the live result stays reproducible --
without the key or a network call.
"""

import json
import os

import voice_honesty_gate  # noqa: F401
from voice_honesty_gate.cli import main

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
LIVE = os.path.join(FIXTURES, "live")


def _fixture(name: str) -> str:
    return os.path.join(FIXTURES, name)


def _live_text(case_file: str) -> str:
    with open(os.path.join(LIVE, case_file), "r", encoding="utf-8") as fh:
        record = json.load(fh)
    final_poll = record["poll_responses"][-1]
    assert final_poll["status"] == "completed"
    return final_poll["text"]


def test_live_json_carries_no_key_material():
    """The raw AssemblyAI responses saved from the live call must never
    carry the API key -- it only ever goes out in the request header, never
    comes back in a response body (see docs/API_NOTES.md)."""
    key_path = "M:/AGENT_VAULT/secrets/assemblyai.key"
    if os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as fh:
            key = fh.read().strip()
        if key:
            for name in ("false_claim_no_tool.json", "confirmed_tool_result.json"):
                raw = open(os.path.join(LIVE, name), "r", encoding="utf-8").read()
                assert key not in raw


def test_live_false_claim_transcript_text_matches_saved_assemblyai_response():
    real_text = _live_text("false_claim_no_tool.json")
    with open(_fixture("live_false_claim.json"), "r", encoding="utf-8") as fh:
        transcript = json.load(fh)
    agent_events = [e for e in transcript["events"] if e["type"] == "transcript.agent"]
    assert agent_events[-1]["text"] == real_text


def test_live_confirmed_transcript_text_matches_saved_assemblyai_response():
    real_text = _live_text("confirmed_tool_result.json")
    with open(_fixture("live_confirmed_booking.json"), "r", encoding="utf-8") as fh:
        transcript = json.load(fh)
    agent_events = [e for e in transcript["events"] if e["type"] == "transcript.agent"]
    assert agent_events[-1]["text"] == real_text


def test_vhg_check_holds_on_the_real_false_claim_transcript(capsys):
    code = main(["check", _fixture("live_false_claim.json")])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["decision"] == "HOLD"
    assert out["findings"][0]["code"] == "FALSE_COMPLETION_CLAIM"


def test_vhg_check_goes_on_the_real_confirmed_transcript(capsys):
    code = main(["check", _fixture("live_confirmed_booking.json")])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["decision"] == "GO"
    assert out["findings"] == []
