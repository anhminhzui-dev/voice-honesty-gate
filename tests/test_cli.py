import json
import os

import voice_honesty_gate  # noqa: F401
from voice_honesty_gate.cli import main

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name: str) -> str:
    return os.path.join(FIXTURES, name)


def test_cli_exit_zero_and_go_on_a_real_tool_run(capsys):
    code = main(["check", _fixture("booking_success.json")])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["decision"] == "GO"
    assert out["coverage"]["status"] == "ALIVE"


def test_cli_exit_two_and_hold_on_claim_with_no_tool(capsys):
    code = main(["check", _fixture("claim_no_tool.json")])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["decision"] == "HOLD"
    assert out["findings"][0]["code"] == "FALSE_COMPLETION_CLAIM"


def test_cli_exit_two_on_malformed_transcript(capsys):
    code = main(["check", _fixture("malformed_missing_events.json")])
    err = capsys.readouterr().err
    assert code == 2
    assert "events" in err
