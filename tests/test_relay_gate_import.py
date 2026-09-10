"""Proves the by-path import wiring in voice_honesty_gate/__init__.py
actually works, rather than assuming it. If relay-gate's src/ ever moves
or the sibling-repo layout changes, this is the test that fails first."""

import voice_honesty_gate  # noqa: F401  (triggers _ensure_relay_gate_on_path)


def test_relay_gate_is_importable_by_path():
    import relay_gate
    from relay_gate.schema import Trajectory

    assert relay_gate.__name__ == "relay_gate"
    t = Trajectory.from_dict({"trajectory_id": "x", "steps": []})
    assert t.trajectory_id == "x"
