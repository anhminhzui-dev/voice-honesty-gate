"""demo: the honest side of the voice-honesty-gate catch.

A tiny scripted voice-agent simulator that produces saved AssemblyAI Voice
Agent transcripts in the exact shape voice_honesty_gate.adapter reads (see
voice_honesty_gate/adapter.py's module docstring and tests/fixtures/*.json
for the schema this package matches). It does not call any real API and
makes no network requests -- it is a fixture generator, sitting next to
the checker it feeds.

    python -m demo.booking_agent --scenario honest --out demo/out/honest.json
    python -m demo.booking_agent --scenario liar   --out demo/out/liar.json

See demo/RUN_DEMO.md for the two judge-facing commands.
"""

from __future__ import annotations

__all__: list[str] = []
