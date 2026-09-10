"""Coverage map for the one ported check, following relay_gate.coverage's
own ALIVE/DEAD contract: does not re-run the check or ask "did it find
something", inspects the same fields the check reads and reports whether
it physically had the data to fire at all.

Two fields, both required for ALIVE (see check_voice_false_completion_claim
in voice_rules.py):

  final_claim   non-empty spoken agent text to evaluate at all
  steps         at least one tool-call event the adapter could place in
                the trajectory -- a transcript with zero tool events has
                no physical evidence to check any claim against, which is
                a different, honest thing to report than "the claim
                happened to not mention completion" (final_claim empty).
"""

from __future__ import annotations

from dataclasses import dataclass

from relay_gate.schema import Trajectory

_FIELD = "final_claim (non-empty) and steps (>=1 adapted tool-call event)"


@dataclass(frozen=True)
class VoiceCoverageResult:
    check: str
    status: str  # "ALIVE" | "DEAD"
    field: str
    detail: str


def voice_coverage(trajectory: Trajectory) -> VoiceCoverageResult:
    if not trajectory.final_claim.strip():
        return VoiceCoverageResult(
            "VOICE_FALSE_COMPLETION_CLAIM",
            "DEAD",
            _FIELD,
            "final_claim is empty -- no spoken agent text was captured in this transcript",
        )
    if not trajectory.steps:
        return VoiceCoverageResult(
            "VOICE_FALSE_COMPLETION_CLAIM",
            "DEAD",
            _FIELD,
            "transcript carries no tool-call events -- nothing to check the claim against",
        )
    return VoiceCoverageResult(
        "VOICE_FALSE_COMPLETION_CLAIM",
        "ALIVE",
        _FIELD,
        f"final_claim present and {len(trajectory.steps)} tool-call step(s) adapted",
    )
