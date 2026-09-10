"""voice_honesty_gate: ports relay-gate's FALSE_COMPLETION_CLAIM check from
text coding-agent trajectories to live AssemblyAI Voice Agent transcripts.

relay-gate is imported as a dependency BY PATH, not pip-installed (build
constraint: no paid API call, no account sign-up, no new pip dependency
beyond the standard library plus relay-gate itself). This module inserts
relay-gate's src/ directory onto sys.path exactly once, at import time,
before any of this package's other modules do `from relay_gate... import
...`.

Default layout assumed (both repos as sibling directories under the same
`repos/` folder):

    repos/
      relay-gate/src/relay_gate/...
      voice-honesty-gate/src/voice_honesty_gate/__init__.py   <- this file

Override with the VHG_RELAY_GATE_SRC environment variable if relay-gate
does not live at that default sibling-repo location.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__version__ = "0.1.0"

# parents[0]=voice_honesty_gate/, [1]=src/, [2]=voice-honesty-gate/, [3]=repos/
_DEFAULT_RELAY_GATE_SRC = Path(__file__).resolve().parents[3] / "relay-gate" / "src"


def _ensure_relay_gate_on_path() -> None:
    try:
        import relay_gate  # noqa: F401

        return  # already importable (pip-installed, or a prior call already wired it)
    except ImportError:
        pass

    override = os.environ.get("VHG_RELAY_GATE_SRC")
    candidate = Path(override) if override else _DEFAULT_RELAY_GATE_SRC

    if not (candidate / "relay_gate").is_dir():
        raise ImportError(
            f"relay_gate package not found at {candidate!s} and is not otherwise importable on sys.path. "
            "voice_honesty_gate imports relay-gate BY PATH (see this file's module docstring): set the "
            "VHG_RELAY_GATE_SRC environment variable to relay-gate's src/ directory, or place relay-gate "
            "as a sibling of this repository under the same repos/ folder, or `pip install` relay-gate."
        )
    sys.path.insert(0, str(candidate))


_ensure_relay_gate_on_path()
