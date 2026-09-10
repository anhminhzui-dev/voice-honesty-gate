"""One-shot runner: the live AssemblyAI end-to-end call that produced
tests/fixtures/live/*.json and LIVE_RECEIPT.md. Not part of the package,
not imported by any test (the offline replay test reads the saved JSON
instead) -- this script is the reproducibility record for how that JSON
was produced, and needs a real key at M:/AGENT_VAULT/secrets/assemblyai.key
to run again.

Usage: python scripts/run_live_call.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from voice_honesty_gate.pre_recorded_client import transcribe_and_wait  # noqa: E402

AUDIO_DIR = REPO_ROOT / "tests" / "fixtures" / "audio"
LIVE_DIR = REPO_ROOT / "tests" / "fixtures" / "live"

CASES = [
    ("false_claim_no_tool", AUDIO_DIR / "false_claim_no_tool.wav"),
    ("confirmed_tool_result", AUDIO_DIR / "confirmed_tool_result.wav"),
]


def _strip_key(obj: dict) -> dict:
    """Defensive: AssemblyAI's documented response shapes carry no key
    material (the key only ever goes out in the request header), but strip
    any field literally named like a credential anyway, and never write
    request headers into the saved JSON."""
    banned = {"authorization", "api_key", "apikey", "key"}
    return {k: v for k, v in obj.items() if k.lower() not in banned}


def main() -> int:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    request_count = 0
    total_audio_seconds = 0.0
    wall_start = time.monotonic()

    for name, audio_path in CASES:
        if not audio_path.exists():
            print(f"missing fixture audio: {audio_path}", file=sys.stderr)
            return 1

        case_start = time.monotonic()
        upload_resp, submit_resp, polls = transcribe_and_wait(audio_path)
        case_elapsed = time.monotonic() - case_start
        # requests this case made: 1 upload + 1 submit + len(polls) GETs
        request_count += 2 + len(polls)

        final = polls[-1]
        total_audio_seconds += float(final.get("audio_duration") or 0.0)

        record = {
            "case": name,
            "audio_path": str(audio_path.relative_to(REPO_ROOT)),
            "wall_seconds": round(case_elapsed, 2),
            "upload_response": _strip_key(upload_resp),
            "submit_response": _strip_key(submit_resp),
            "poll_responses": [_strip_key(p) for p in polls],
        }
        out_path = LIVE_DIR / f"{name}.json"
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"{name}: status={final.get('status')} audio_duration={final.get('audio_duration')}s "
              f"polls={len(polls)} wall={case_elapsed:.1f}s -> {out_path}")

    wall_total = time.monotonic() - wall_start
    print(f"\nTOTAL requests={request_count} audio_seconds={total_audio_seconds:.1f} wall={wall_total:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
