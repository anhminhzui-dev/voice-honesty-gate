import json
import os

import voice_honesty_gate  # noqa: F401  (wires relay_gate onto sys.path, see its __init__.py)
from demo.booking_agent import SPOKEN_COMPLETION_CLAIM, build_transcript, main
from voice_honesty_gate.adapter import events_to_trajectory
from voice_honesty_gate.cli import main as vhg_main
from voice_honesty_gate.voice_rules import check_voice_false_completion_claim

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests", "fixtures")


def _fixture(name: str) -> str:
    return os.path.join(FIXTURES, name)


def _required_transcript_keys(path: str) -> set:
    with open(path, "r", encoding="utf-8") as fh:
        return set(json.load(fh).keys())


def _required_event_keys(path: str) -> set:
    with open(path, "r", encoding="utf-8") as fh:
        events = json.load(fh)["events"]
    keys: set = set()
    for ev in events:
        keys |= set(ev.keys())
    return keys


# ---------------------------------------------------------------------------
# schema: the generated transcript matches the existing fixtures' shape
# ---------------------------------------------------------------------------


def test_honest_transcript_top_level_keys_match_fixture(tmp_path):
    out = tmp_path / "honest.json"
    assert main(["--scenario", "honest", "--out", str(out)]) == 0

    generated_keys = _required_transcript_keys(str(out))
    fixture_keys = _required_transcript_keys(_fixture("booking_success.json"))
    # required keys the adapter actually reads (adapter.py: session_id/
    # trajectory_id fallback, "events" is mandatory)
    assert {"session_id", "events"} <= generated_keys
    assert {"session_id", "events"} <= fixture_keys


def test_honest_transcript_event_shapes_match_adapter_vocabulary(tmp_path):
    out = tmp_path / "honest.json"
    main(["--scenario", "honest", "--out", str(out)])

    with open(out, "r", encoding="utf-8") as fh:
        events = json.load(fh)["events"]

    by_type = {ev["type"]: ev for ev in events}
    assert "tool.call" in by_type
    assert "tool.result" in by_type
    assert "transcript.agent" in by_type

    call = by_type["tool.call"]
    assert {"type", "call_id", "name", "arguments"} <= set(call.keys())

    result = by_type["tool.result"]
    assert {"type", "call_id", "result", "is_error"} <= set(result.keys())
    assert result["call_id"] == call["call_id"]
    assert result["is_error"] is False

    agent = by_type["transcript.agent"]
    assert {"type", "text"} <= set(agent.keys())
    assert agent["text"] == SPOKEN_COMPLETION_CLAIM


def test_liar_transcript_has_no_tool_events_but_same_spoken_claim(tmp_path):
    out = tmp_path / "liar.json"
    main(["--scenario", "liar", "--out", str(out)])

    with open(out, "r", encoding="utf-8") as fh:
        events = json.load(fh)["events"]

    types = [ev["type"] for ev in events]
    assert "tool.call" not in types
    assert "tool.result" not in types

    agent_texts = [ev["text"] for ev in events if ev["type"] == "transcript.agent"]
    assert agent_texts[-1] == SPOKEN_COMPLETION_CLAIM


def test_honest_and_liar_speak_the_identical_completion_claim(tmp_path):
    # The whole point of the demo: only the tool-call evidence differs.
    honest_out = tmp_path / "honest.json"
    liar_out = tmp_path / "liar.json"
    main(["--scenario", "honest", "--out", str(honest_out)])
    main(["--scenario", "liar", "--out", str(liar_out)])

    def last_claim(path):
        with open(path, "r", encoding="utf-8") as fh:
            events = json.load(fh)["events"]
        return [e["text"] for e in events if e["type"] == "transcript.agent"][-1]

    assert last_claim(honest_out) == last_claim(liar_out) == SPOKEN_COMPLETION_CLAIM


# ---------------------------------------------------------------------------
# --tool-log: adapter-shaped, confirmed-only
# ---------------------------------------------------------------------------


def test_honest_tool_log_carries_one_confirmed_result_in_adapter_shape(tmp_path):
    out = tmp_path / "honest.json"
    tool_log_path = tmp_path / "honest_tool_log.json"
    main(["--scenario", "honest", "--out", str(out), "--tool-log", str(tool_log_path)])

    with open(tool_log_path, "r", encoding="utf-8") as fh:
        tool_log = json.load(fh)

    assert isinstance(tool_log, list)
    assert len(tool_log) == 1
    entry = tool_log[0]
    assert {"call_id", "name", "arguments", "result", "is_error"} <= set(entry.keys())
    assert entry["is_error"] is False
    assert "confirmed" in entry["result"]


def test_liar_tool_log_is_an_empty_list(tmp_path):
    out = tmp_path / "liar.json"
    tool_log_path = tmp_path / "liar_tool_log.json"
    main(["--scenario", "liar", "--out", str(out), "--tool-log", str(tool_log_path)])

    with open(tool_log_path, "r", encoding="utf-8") as fh:
        tool_log = json.load(fh)

    assert tool_log == []


def test_tool_log_is_not_written_when_flag_omitted(tmp_path):
    out = tmp_path / "honest.json"
    tool_log_path = tmp_path / "honest_tool_log.json"
    main(["--scenario", "honest", "--out", str(out)])
    assert not tool_log_path.exists()


# ---------------------------------------------------------------------------
# the real catch: the existing, unmodified gate's verdict on each scenario
# ---------------------------------------------------------------------------


def test_honest_scenario_loads_as_a_valid_trajectory_with_a_confirmed_step():
    transcript, _ = build_transcript("honest", "call-demo-honest")
    assert transcript["session_id"] == "call-demo-honest"
    traj = events_to_trajectory(transcript["session_id"], transcript["events"])
    assert len(traj.steps) == 1
    assert not traj.steps[0].output.startswith(("ERROR:", "PENDING:"))
    findings = check_voice_false_completion_claim(traj)
    assert findings == []


def test_liar_scenario_fires_false_completion_claim():
    transcript, _ = build_transcript("liar", "call-demo-liar")
    traj = events_to_trajectory(transcript["session_id"], transcript["events"])
    assert traj.steps == ()
    findings = check_voice_false_completion_claim(traj)
    assert len(findings) == 1
    assert findings[0].reason.value == "FALSE_COMPLETION_CLAIM"
    assert findings[0].category == "hold"


def test_cli_check_returns_go_on_honest_scenario_output(tmp_path, capsys):
    out = tmp_path / "honest.json"
    main(["--scenario", "honest", "--out", str(out)])
    capsys.readouterr()  # discard demo.booking_agent's own confirmation print

    code = vhg_main(["check", str(out)])
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result["decision"] == "GO"
    assert result["findings"] == []


def test_cli_check_returns_hold_with_false_completion_claim_on_liar_scenario_output(tmp_path, capsys):
    out = tmp_path / "liar.json"
    main(["--scenario", "liar", "--out", str(out)])
    capsys.readouterr()  # discard demo.booking_agent's own confirmation print

    code = vhg_main(["check", str(out)])
    result = json.loads(capsys.readouterr().out)

    assert code == 2
    assert result["decision"] == "HOLD"
    assert result["findings"][0]["code"] == "FALSE_COMPLETION_CLAIM"


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def test_unknown_scenario_raises_value_error():
    import pytest

    with pytest.raises(ValueError, match="unknown scenario"):
        build_transcript("skeptic", "call-x")


def test_main_prints_a_confirmation_line(tmp_path, capsys):
    out = tmp_path / "honest.json"
    main(["--scenario", "honest", "--out", str(out)])
    printed = capsys.readouterr().out
    assert str(out) in printed
    assert "honest" in printed
