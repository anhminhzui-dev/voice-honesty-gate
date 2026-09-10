"""Command-line entry point.

    vhg check <transcript.json>
    python -m voice_honesty_gate.cli check <transcript.json>

    vhg live [--seconds 30] [--tool-log path.json]
    vhg live --from-wav path.wav [--tool-log path.json]
    python -m voice_honesty_gate.cli live ...

`check` loads a saved AssemblyAI Voice Agent transcript (fixture mode; see
adapter.py and README.md for the live-key path), runs the ported
FALSE_COMPLETION_CLAIM check, and prints the check result plus the
ALIVE/DEAD coverage verdict for that one check as JSON.

`live` captures a real microphone (or replays a WAV file with
`--from-wav`, the code path every test in this repo drives), streams it to
AssemblyAI's real-time Streaming Speech-to-Text WebSocket
(streaming_client.py; endpoint/auth/message shapes cited in
docs/LIVE_MIC.md), prints each final transcript turn as it arrives, and
runs the SAME `check_voice_false_completion_claim` used by `check` on the
accumulating transcript against a tool log (`tool_log.py`; default: empty,
so any spoken completion claim is unbacked and yields HOLD). See
live_session.py for the session loop. Writes a session receipt JSON under
live_sessions/.

Exit code: 0 on GO, 2 on HOLD or AMBIGUOUS-HOLD (fails closed, same
convention relay_gate.cli uses) or a malformed transcript file.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

from voice_honesty_gate.adapter import load_transcript
from voice_honesty_gate.coverage import voice_coverage
from voice_honesty_gate.errors import MalformedTranscriptError, NoApiKeyError
from voice_honesty_gate.voice_rules import check_voice_false_completion_claim

LIVE_SESSIONS_DIR = pathlib.Path("live_sessions")


def _run_check(path: str) -> tuple[dict, int]:
    trajectory = load_transcript(path)
    findings = check_voice_false_completion_claim(trajectory)
    cov = voice_coverage(trajectory)

    hold = [f for f in findings if f.category == "hold"]
    ambiguous = [f for f in findings if f.category == "ambiguous"]
    if hold:
        decision = "HOLD"
    elif ambiguous:
        decision = "AMBIGUOUS-HOLD"  # no judge wired in this scaffold: fails closed, same as relay_gate.gate
    else:
        decision = "GO"

    result = {
        "session_id": trajectory.trajectory_id,
        "decision": decision,
        "findings": [{"code": f.reason.value, "category": f.category, "detail": f.detail} for f in findings],
        "coverage": {
            "check": cov.check,
            "status": cov.status,
            "field": cov.field,
            "detail": cov.detail,
        },
    }
    return result, (0 if decision == "GO" else 2)


def _run_live(args: argparse.Namespace, out_dir: pathlib.Path = LIVE_SESSIONS_DIR) -> int:
    from voice_honesty_gate.audio_capture import mic_chunks, wav_chunks
    from voice_honesty_gate.live_session import run_live_session
    from voice_honesty_gate.tool_log import load_tool_log_events

    tool_log_events = load_tool_log_events(args.tool_log)  # [] by default, see tool_log.py

    if args.from_wav:
        sample_rate, chunks = wav_chunks(args.from_wav)
        session_id = f"live-fromwav-{pathlib.Path(args.from_wav).stem}"
    else:
        sample_rate, chunks = mic_chunks(args.seconds)
        session_id = "live-mic"

    receipt = run_live_session(
        chunks,
        sample_rate,
        tool_log_events=tool_log_events,
        session_id=session_id,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{session_id}_{stamp}.json"
    out_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"session receipt written to {out_path}")

    return 0 if receipt["decision"] == "GO" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vhg")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="check one saved voice transcript for a false completion claim")
    check.add_argument("path", help="path to a saved transcript JSON file (see adapter.py for the shape)")

    live = sub.add_parser(
        "live",
        help="stream microphone (or --from-wav) audio to AssemblyAI's Streaming Speech-to-Text API "
        "and check the accumulating transcript for a false completion claim",
    )
    live.add_argument("--seconds", type=float, default=30.0, help="microphone capture duration (ignored with --from-wav)")
    live.add_argument("--tool-log", default=None, help="path to a tool-log JSON (see tool_log.py); default: empty")
    live.add_argument("--from-wav", default=None, help="replay a WAV file instead of capturing the microphone")

    args = parser.parse_args(argv)

    if args.command == "check":
        try:
            result, code = _run_check(args.path)
        except MalformedTranscriptError as exc:
            print(f"voice-honesty-gate: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2))
        return code

    if args.command == "live":
        try:
            return _run_live(args)
        except (MalformedTranscriptError, NoApiKeyError, ImportError) as exc:
            print(f"voice-honesty-gate: {exc}", file=sys.stderr)
            return 2

    return 1


if __name__ == "__main__":
    sys.exit(main())
