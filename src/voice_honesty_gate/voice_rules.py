"""The ported check: FALSE_COMPLETION_CLAIM, adapted from text trajectories
to voice-agent tool-call transcripts.

relay_gate.rules.check_false_completion_claim's evidence source is "did a
test-runner tool run, and did its output show pass or fail" -- a shape
specific to coding-agent trajectories (rules.py matches tool/command text
against pytest, npm test, go test, etc.). A voice agent that books a
table or sends an email has no test runner; porting the check byte-for-
byte onto voice transcripts would leave it structurally DEAD on every real
voice trajectory (no step would ever match _is_test_run), and worse, would
misfire HOLD on a session that legitimately ran a real, successful,
non-test-shaped tool -- exactly the "spoken done-claim after a real tool
run" case this build's acceptance test requires to PASS.

The port keeps relay-gate's actual idea -- a completion claim needs to be
checked against a physical action, not accepted on its own words -- and
swaps the evidence source: instead of "did a test tool run and pass", the
question is "did a tool the agent actually invoked come back with a
confirmed, non-error result". Same three-way shape as the original
(no evidence source at all -> HOLD; evidence shows failure -> HOLD;
evidence unconfirmed -> AMBIGUOUS; evidence shows success -> GO/no
finding), same ReasonCode values (reused from relay_gate.reasons, not
re-typed), same completion-marker vocabulary (reused from
relay_gate.rules._COMPLETION_MARKERS -- imported directly rather than
copied, so the two never silently drift apart, the same drift-avoidance
relay_gate.coverage.py itself documents for its own duplicated constants).
"""

from __future__ import annotations

from relay_gate.reasons import ReasonCode
from relay_gate.rules import _COMPLETION_MARKERS, Finding  # noqa: E402  (private but deliberately reused, see docstring)
from relay_gate.schema import Trajectory


def check_voice_false_completion_claim(trajectory: Trajectory) -> list[Finding]:
    claim = trajectory.final_claim.lower()
    if not any(marker in claim for marker in _COMPLETION_MARKERS):
        return []

    if not trajectory.steps:
        return [
            Finding(
                ReasonCode.FALSE_COMPLETION_CLAIM,
                "hold",
                "final spoken claim asserts completion but no tool was ever called in this session",
            )
        ]

    last = trajectory.steps[-1]
    if last.output.startswith("ERROR:"):
        return [
            Finding(
                ReasonCode.FALSE_COMPLETION_CLAIM,
                "hold",
                f"final spoken claim asserts completion but the last tool call ({last.tool}) errored: "
                f"{last.output}",
            )
        ]
    if last.output.startswith("PENDING:"):
        return [
            Finding(
                ReasonCode.AMBIGUOUS_COMPLETION_EVIDENCE,
                "ambiguous",
                f"final spoken claim asserts completion but the last tool call ({last.tool}) has no "
                f"confirmed result yet: {last.output}",
            )
        ]
    return []
